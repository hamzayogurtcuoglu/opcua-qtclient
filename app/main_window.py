"""Main window — orchestrates all panels, toolbar, and connections."""

import asyncio
import json
import os
import logging
from typing import Optional

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction, QFont, QIcon
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QToolBar, QToolButton, QSplitter, QTabWidget,
    QStatusBar, QLabel, QPushButton, QMessageBox,
    QApplication, QDockWidget, QSizePolicy, QFileDialog,
    QStackedWidget,
)

from app.models import (
    ServerInfo, ConnectionStatus, NodeType, FavoriteItem, HistoryEntry,
)
from app.opcua_client import OpcUaClient
from app.theme import Colors, theme_manager
from app.widgets.server_panel import ServerPanel
from app.widgets.connection_tab import ConnectionTab
from app.widgets.favorites_panel import FavoritesPanel
from app.widgets.script_runner import ScriptRunnerPanel
from app.widgets.scene3d import Scene3DPanel
from app.dialogs.add_server_dialog import AddServerDialog
from app.dialogs.discovery_dialog import DiscoveryDialog
from app.dialogs.settings_dialog import SettingsDialog

logger = logging.getLogger(__name__)

SERVERS_FILE = os.path.join(os.path.expanduser("~"), ".opcua_client_servers.json")
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".opcua_client_settings.json")


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self._clients: dict[str, OpcUaClient] = {}  # url -> client
        self._tabs: dict[str, ConnectionTab] = {}     # url -> tab
        self._settings: dict = {}
        self._last_selected_node: str = ""
        self._load_settings()
        
        # Apply theme from settings before setting up UI
        theme = self._settings.get("theme", "system")
        theme_manager.apply_theme(theme)
        
        self._setup_ui()
        self._load_servers()
        
        # Connect to theme changes
        theme_manager.theme_changed.connect(self.update_theme)

    def _setup_ui(self):
        self.setWindowTitle("OPC UA Client")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Toolbar
        self._create_toolbar()

        # Content area
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(8)

        # Central split view: Servers/Favorites | Tabs
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)

        # Left: Server list
        self.server_panel = ServerPanel()
        self.server_panel.server_connect_requested.connect(self._on_connect_server)
        self.server_panel.server_disconnect_requested.connect(self._on_disconnect_server)
        self.server_panel.server_clicked.connect(self._on_server_clicked)
        self.server_panel.server_edit_requested.connect(self._on_edit_server)
        self.server_panel.add_server_requested.connect(self._on_add_server)

        # Favorites now live in the same left sidebar, toggled via a segmented
        # control, instead of a floating dock.
        self.favorites_panel = FavoritesPanel()
        self.favorites_panel.favorite_clicked.connect(self._on_favorite_clicked)
        self.favorites_panel.favorite_execute.connect(self._on_favorite_execute)

        self.left_sidebar = self._build_left_sidebar()
        self.main_splitter.addWidget(self.left_sidebar)

        # Center: Tabs (Address spaces)
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.tabCloseRequested.connect(self._on_tab_close)

        # Add "+" button for new connection
        self.add_tab_btn = QPushButton("+")
        self.add_tab_btn.setFixedSize(28, 28)
        self.add_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_tab_btn.setToolTip("Add a new server connection")
        self.add_tab_btn.clicked.connect(self._on_add_server)
        self.tab_widget.setCornerWidget(self.add_tab_btn, Qt.Corner.TopRightCorner)

        self.main_splitter.addWidget(self.tab_widget)
        self.main_splitter.setSizes([280, 1000])
        # Keep the left sidebar slim and let the address space take the space
        # proportionally when the window is resized.
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)

        content_layout.addWidget(self.main_splitter)
        main_layout.addWidget(content_widget)

        # ── Floating Dock: Script Runner ──────────────────────────────────────
        self.script_runner_panel = ScriptRunnerPanel()
        self.script_runner_panel.add_to_favorites.connect(
            lambda path, name, args, content: self.favorites_panel.add_script_favorite(path, name, args, content)
        )

        self.runner_dock = QDockWidget("▶  Script Runner", self)
        self.runner_dock.setWidget(self.script_runner_panel)
        self.runner_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea |
            Qt.DockWidgetArea.RightDockWidgetArea |
            Qt.DockWidgetArea.BottomDockWidgetArea |
            Qt.DockWidgetArea.NoDockWidgetArea
        )
        self.runner_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.runner_dock.setFloating(True)
        self.runner_dock.resize(480, 600)
        self.runner_dock.move(
            self.x() + self.width() - 520,
            self.y() + 80
        )
        self.runner_dock.hide()
        self.runner_dock.visibilityChanged.connect(self._on_runner_dock_visibility)

        # ── Floating Dock: Subscriptions ──────────────────────────────────────
        from app.widgets.subscriptions_panel import SubscriptionsPanel
        self.subs_panel = SubscriptionsPanel()
        self.subs_panel.unsubscribe_requested.connect(self._on_unsubscribe_requested)
        self.subs_panel.clear_btn.clicked.connect(self._on_clear_subscriptions)

        self.subs_dock = QDockWidget("📡  Subscriptions", self)
        self.subs_dock.setWidget(self.subs_panel)
        self.subs_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea |
            Qt.DockWidgetArea.RightDockWidgetArea |
            Qt.DockWidgetArea.BottomDockWidgetArea |
            Qt.DockWidgetArea.NoDockWidgetArea
        )
        self.subs_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.subs_dock.setFloating(True)
        self.subs_dock.resize(480, 300)
        self.subs_dock.move(
            self.x() + self.width() - 520,
            self.y() + 400
        )
        self.subs_dock.hide()
        self.subs_dock.visibilityChanged.connect(self._on_subs_dock_visibility)

        # ── Floating Dock: 3D Scene Builder ───────────────────────────────────
        self.scene3d_panel = Scene3DPanel()
        self.scene3d_panel.set_node_picker(self._active_node_picker)

        self.scene3d_dock = QDockWidget("🧊  3D Scene Builder", self)
        self.scene3d_dock.setWidget(self.scene3d_panel)
        self.scene3d_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea |
            Qt.DockWidgetArea.RightDockWidgetArea |
            Qt.DockWidgetArea.BottomDockWidgetArea |
            Qt.DockWidgetArea.NoDockWidgetArea
        )
        self.scene3d_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.scene3d_dock.setFloating(True)
        self.scene3d_dock.resize(1100, 720)
        self.scene3d_dock.move(self.x() + 160, self.y() + 120)
        self.scene3d_dock.hide()
        self.scene3d_dock.visibilityChanged.connect(self._on_scene3d_dock_visibility)

        # Keep the 3D scene bound to whichever connection tab is active.
        self.tab_widget.currentChanged.connect(self._on_active_tab_changed)

        # Status bar
        self.statusBar().showMessage("Ready — No active connections")

        # Initial style setup
        self.update_theme()

    def _build_left_sidebar(self) -> QWidget:
        """Build the left sidebar: a Servers/Favorites toggle over a stack."""
        container = QWidget()
        container.setMinimumWidth(240)
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        # Segmented toggle
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(0)
        self.sidebar_servers_btn = QPushButton("🖧  Servers")
        self.sidebar_favorites_btn = QPushButton("★  Favorites")
        for btn in (self.sidebar_servers_btn, self.sidebar_favorites_btn):
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.sidebar_servers_btn.setChecked(True)
        self.sidebar_servers_btn.clicked.connect(lambda: self._show_sidebar_view(0))
        self.sidebar_favorites_btn.clicked.connect(lambda: self._show_sidebar_view(1))
        toggle_row.addWidget(self.sidebar_servers_btn)
        toggle_row.addWidget(self.sidebar_favorites_btn)
        v.addLayout(toggle_row)

        # Stack
        self.left_stack = QStackedWidget()
        self.left_stack.addWidget(self.server_panel)     # index 0
        self.left_stack.addWidget(self.favorites_panel)  # index 1
        v.addWidget(self.left_stack, 1)

        return container

    def _show_sidebar_view(self, index: int):
        """Switch the left sidebar between Servers (0) and Favorites (1)."""
        self.left_stack.setCurrentIndex(index)
        self.sidebar_servers_btn.setChecked(index == 0)
        self.sidebar_favorites_btn.setChecked(index == 1)
        # Keep the toolbar Favorites button in sync.
        if hasattr(self, "fav_btn"):
            self.fav_btn.blockSignals(True)
            self.fav_btn.setChecked(index == 1)
            self.fav_btn.blockSignals(False)
        self._style_sidebar_toggle()

    def _style_sidebar_toggle(self):
        """Apply themed styling to the Servers/Favorites segmented control."""
        def style_for(active: bool) -> str:
            if active:
                return f"""
                    QPushButton {{
                        background-color: {Colors.ACCENT};
                        color: #ffffff;
                        border: 1px solid {Colors.ACCENT};
                        padding: 9px 10px;
                        font-size: 13px;
                        font-weight: 700;
                    }}
                """
            return f"""
                QPushButton {{
                    background-color: {Colors.BG_CARD};
                    color: {Colors.TEXT_SECONDARY};
                    border: 1px solid {Colors.BORDER};
                    padding: 9px 10px;
                    font-size: 13px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    color: {Colors.TEXT_PRIMARY};
                    background-color: {Colors.BG_HOVER};
                }}
            """
        # Rounded outer corners only, to look like one segmented control.
        servers_active = self.sidebar_servers_btn.isChecked()
        self.sidebar_servers_btn.setStyleSheet(
            style_for(servers_active).replace(
                "QPushButton {", "QPushButton { border-top-left-radius: 9px; border-bottom-left-radius: 9px; border-right: none;", 1
            )
        )
        self.sidebar_favorites_btn.setStyleSheet(
            style_for(not servers_active).replace(
                "QPushButton {", "QPushButton { border-top-right-radius: 9px; border-bottom-right-radius: 9px;", 1
            )
        )

    def update_theme(self):
        """Update inline styles when theme changes."""
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background-color: transparent;
            }}
            QTabBar::tab {{
                padding: 8px 20px;
                font-size: 12px;
            }}
        """)

        dock_title_style = f"""
            QDockWidget {{
                font-weight: bold;
                color: {Colors.TEXT_PRIMARY};
                background-color: {Colors.BG_DARK};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
            }}
            QDockWidget::title {{
                background-color: {Colors.BG_CARD};
                padding: 6px 10px;
                border-bottom: 1px solid {Colors.BORDER};
                border-radius: 0;
                font-weight: bold;
                color: {Colors.TEXT_PRIMARY};
            }}
            QDockWidget::close-button {{
                background: transparent;
                border: none;
                padding: 2px;
            }}
        """
        if hasattr(self, 'fav_dock'):
            self.fav_dock.setStyleSheet(dock_title_style)
        if hasattr(self, 'runner_dock'):
            self.runner_dock.setStyleSheet(dock_title_style)
        if hasattr(self, 'subs_dock'):
            self.subs_dock.setStyleSheet(dock_title_style)

        if hasattr(self, 'sidebar_servers_btn'):
            self._style_sidebar_toggle()

        self.add_tab_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {Colors.TEXT_SECONDARY};
                font-size: 18px;
                font-weight: bold;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {Colors.BG_HOVER};
                color: {Colors.TEXT_PRIMARY};
            }}
        """)

        self.statusBar().setStyleSheet(f"""
            QStatusBar {{
                background-color: {Colors.BG_DARK};
                color: {Colors.TEXT_SECONDARY};
                border-top: 1px solid {Colors.BORDER};
                padding: 2px 10px;
                font-size: 11px;
            }}
        """)

        self.toolbar.setStyleSheet(f"""
            QToolBar {{
                background-color: {Colors.BG_CARD};
                border: none;
                border-bottom: 1px solid {Colors.BORDER};
                padding: 7px 14px;
                spacing: 4px;
            }}
            QToolBar::separator {{
                background-color: {Colors.BORDER};
                width: 1px;
                margin: 6px 10px;
            }}
            QToolButton {{
                background-color: transparent;
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid transparent;
                border-radius: 8px;
                padding: 7px 13px;
                font-size: 13px;
                font-weight: 500;
            }}
            QToolButton:hover {{
                background-color: {Colors.BG_HOVER};
                border: 1px solid {Colors.BORDER};
                color: {Colors.TEXT_PRIMARY};
            }}
            QToolButton:pressed {{
                background-color: {Colors.BG_SURFACE};
            }}
            QToolButton:checked {{
                background-color: {Colors.ACCENT};
                border: 1px solid {Colors.ACCENT};
                color: #ffffff;
            }}
            QToolButton:checked:hover {{
                background-color: {Colors.ACCENT_HOVER};
                border: 1px solid {Colors.ACCENT_HOVER};
            }}
        """)

        self.title_label.setStyleSheet(f"""
            font-size: 15px;
            font-weight: 800;
            color: {Colors.ACCENT};
            background: transparent;
            padding: 0 12px 0 4px;
            letter-spacing: 0.3px;
        """)

        # Update toggle button text if theme changes
        if hasattr(self, 'theme_btn'):
            if theme_manager.current_mode == "light":
                self.theme_btn.setText("🌙 Dark Mode")
            else:
                self.theme_btn.setText("☀️ Light Mode")

    def _create_toolbar(self):
        """Create the top toolbar."""
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.toolbar.setIconSize(QSize(18, 18))

        # App title
        self.title_label = QLabel("  OPC UA Client  ")
        self.toolbar.addWidget(self.title_label)

        self.toolbar.addSeparator()

        # Find Server
        discover_btn = QToolButton()
        discover_btn.setText("⌕ Find Server")
        discover_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        discover_btn.clicked.connect(self._on_discover)
        self.toolbar.addWidget(discover_btn)

        # Refresh
        refresh_btn = QToolButton()
        refresh_btn.setText("↻ Refresh Connections")
        refresh_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        refresh_btn.clicked.connect(self._on_refresh_all)
        self.toolbar.addWidget(refresh_btn)

        # Spacer
        spacer = QWidget()
        spacer.setStyleSheet("background: transparent;")
        spacer.setSizePolicy(spacer.sizePolicy().horizontalPolicy(), spacer.sizePolicy().verticalPolicy())
        from PyQt6.QtWidgets import QSizePolicy
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(spacer)

        # Favorites toggle
        self.fav_btn = QToolButton()
        self.fav_btn.setText("★ Favorites")
        self.fav_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.fav_btn.setCheckable(True)
        self.fav_btn.setChecked(False)
        self.fav_btn.toggled.connect(self._toggle_favorites)
        self.toolbar.addWidget(self.fav_btn)

        # Script Runner toggle
        self.script_runner_btn = QToolButton()
        self.script_runner_btn.setText("▶ Script Runner")
        self.script_runner_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.script_runner_btn.setCheckable(True)
        self.script_runner_btn.setChecked(False)
        self.script_runner_btn.toggled.connect(self._toggle_script_runner)
        self.toolbar.addWidget(self.script_runner_btn)

        # Subscriptions toggle
        self.subs_btn = QToolButton()
        self.subs_btn.setText("📡 Subscriptions")
        self.subs_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.subs_btn.setCheckable(True)
        self.subs_btn.setChecked(False)
        self.subs_btn.toggled.connect(self._toggle_subscriptions)
        self.toolbar.addWidget(self.subs_btn)

        # 3D Scene Builder toggle
        self.scene3d_btn = QToolButton()
        self.scene3d_btn.setText("🧊 3D Scene")
        self.scene3d_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.scene3d_btn.setCheckable(True)
        self.scene3d_btn.setChecked(False)
        self.scene3d_btn.toggled.connect(self._toggle_scene3d)
        self.toolbar.addWidget(self.scene3d_btn)

        self.toolbar.addSeparator()

        # Import/Export
        import_btn = QToolButton()
        import_btn.setText("⬇ Import")
        import_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        import_btn.clicked.connect(self._on_import_config)
        self.toolbar.addWidget(import_btn)

        export_btn = QToolButton()
        export_btn.setText("⬆ Export")
        export_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        export_btn.clicked.connect(self._on_export_config)
        self.toolbar.addWidget(export_btn)

        self.toolbar.addSeparator()

        # Settings
        settings_btn = QToolButton()
        settings_btn.setText("⚙ Settings")
        settings_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        settings_btn.clicked.connect(self._on_settings)
        self.toolbar.addWidget(settings_btn)

        self.addToolBar(self.toolbar)

    # ---- Server Management ----

    def _on_add_server(self):
        """Show dialog to add a new server."""
        dialog = AddServerDialog(self)
        if dialog.exec():
            server = dialog.get_result()
            if server:
                self.server_panel.add_server(server)
                self._save_servers()
                self.statusBar().showMessage(f"Added server: {server.name}")

    def _on_edit_server(self, server_info: ServerInfo):
        """Show dialog to edit an existing server."""
        dialog = AddServerDialog(self, edit_server=server_info)
        if dialog.exec():
            new_info = dialog.get_result()
            if new_info:
                self.server_panel.update_server(server_info.url, new_info)
                self._save_servers()
                self.statusBar().showMessage(f"Updated server: {new_info.name}")

    def _on_discover(self):
        """Show server discovery dialog."""
        dialog = DiscoveryDialog(self)
        if dialog.exec():
            servers = dialog.get_selected_servers()
            for server in servers:
                self.server_panel.add_server(server)
            self._save_servers()
            self.statusBar().showMessage(f"Added {len(servers)} server(s) from discovery")

    def _on_connect_server(self, server_info: ServerInfo):
        """Connect to a server and open a new tab."""
        asyncio.ensure_future(self._connect_server(server_info))

    async def _connect_server(self, server_info: ServerInfo):
        """Async connection handler."""
        url = server_info.url

        # Check if already connected
        if url in self._clients and self._clients[url].is_connected:
            # Just switch to the existing tab
            if url in self._tabs:
                idx = self.tab_widget.indexOf(self._tabs[url])
                if idx >= 0:
                    self.tab_widget.setCurrentIndex(idx)
            return

        self.statusBar().showMessage(f"Connecting to {server_info.name}...")
        self.server_panel.update_server_status(url, ConnectionStatus.CONNECTING)

        # Create client
        client = OpcUaClient(self, request_timeout=600.0, watchdog_interval=600.0)
        client.connection_changed.connect(
            lambda u, s: self.server_panel.update_server_status(u, s)
        )
        client.error_occurred.connect(self._on_error)
        client.data_changed.connect(
            lambda nid, nname, val, s=server_info.name: self.subs_panel.add_or_update_item(s, nid, nname, val)
        )

        success = await client.connect(
            url,
            security_policy=server_info.security_policy,
            username=server_info.username,
            password=server_info.password,
            timeout=self._settings.get("timeout", 10),
        )

        if success:
            self._clients[url] = client

            # Create connection tab
            tab = ConnectionTab(server_info.name, url, client)
            tab.disconnect_requested.connect(self._on_disconnect_url)
            tab.add_to_favorites.connect(
                lambda nid, name, ntype, args, _url=url, _sn=server_info.name, _tab=tab:
                    asyncio.ensure_future(
                        self._add_favorite_with_path(_tab, _url, _sn, nid, name, ntype, args)
                    )
            )
            self._tabs[url] = tab

            idx = self.tab_widget.addTab(tab, f"● {server_info.name}")
            self.tab_widget.setCurrentIndex(idx)

            # Track node selection so the 3D Scene Builder can bind the
            # currently selected node, and bind the scene to this client.
            tab.address_tree.node_selected.connect(self._on_dash_node_selected)
            self.scene3d_panel.set_client(client)

            # Load address space
            await tab.load_address_space()
            self.statusBar().showMessage(f"Connected to {server_info.name}")
        else:
            self.statusBar().showMessage(f"Failed to connect to {server_info.name}")

    def _on_disconnect_server(self, server_info: ServerInfo):
        """Disconnect from a server."""
        asyncio.ensure_future(self._disconnect_server(server_info.url))

    def _on_disconnect_url(self, url: str):
        asyncio.ensure_future(self._disconnect_server(url))

    async def _disconnect_server(self, url: str):
        """Async disconnect handler."""
        if url in self._clients:
            await self._clients[url].disconnect()
            del self._clients[url]

        if url in self._tabs:
            tab = self._tabs[url]
            idx = self.tab_widget.indexOf(tab)
            if idx >= 0:
                self.tab_widget.removeTab(idx)
            tab.deleteLater()
            del self._tabs[url]

        self.server_panel.update_server_status(url, ConnectionStatus.DISCONNECTED)
        self.statusBar().showMessage(f"Disconnected from {url}")

    def _on_server_clicked(self, server_info: ServerInfo):
        """When a server card is clicked, switch to its tab if connected."""
        if server_info.status == ConnectionStatus.CONNECTED and server_info.url in self._tabs:
            tab = self._tabs[server_info.url]
            idx = self.tab_widget.indexOf(tab)
            if idx >= 0:
                self.tab_widget.setCurrentIndex(idx)
        elif server_info.status != ConnectionStatus.CONNECTED:
            # Auto-connect on click
            self._on_connect_server(server_info)

    def _on_tab_close(self, index: int):
        """Handle tab close button."""
        widget = self.tab_widget.widget(index)
        if isinstance(widget, ConnectionTab):
            asyncio.ensure_future(self._disconnect_server(widget.server_url))

    # ---- Toolbar Actions ----

    def _on_refresh_all(self):
        """Refresh all connected servers' address spaces."""
        for url, tab in self._tabs.items():
            if url in self._clients and self._clients[url].is_connected:
                asyncio.ensure_future(tab.load_address_space())
        self.statusBar().showMessage("Refreshed all connections")

    def _toggle_favorites(self, checked: bool):
        """Toolbar Favorites button — switch the left sidebar view."""
        self._show_sidebar_view(1 if checked else 0)

    def _on_fav_dock_visibility(self, visible: bool):
        """Kept for backwards compatibility (favorites are now in the sidebar)."""
        if hasattr(self, 'fav_btn'):
            self.fav_btn.blockSignals(True)
            self.fav_btn.setChecked(visible)
            self.fav_btn.blockSignals(False)

    def _toggle_script_runner(self, visible: bool):
        """Toggle Script Runner pop-up dock."""
        if visible:
            self.runner_dock.show()
            self.runner_dock.raise_()
        else:
            self.runner_dock.hide()

    def _on_subs_dock_visibility(self, visible: bool):
        self.subs_btn.blockSignals(True)
        self.subs_btn.setChecked(visible)
        self.subs_btn.blockSignals(False)

    def _toggle_subscriptions(self, checked: bool):
        if checked:
            self.subs_dock.show()
            self.subs_dock.raise_()
        else:
            self.subs_dock.hide()

    # ---- 3D Scene Builder ----

    def _toggle_scene3d(self, checked: bool):
        if checked:
            self.scene3d_panel.set_client(self._active_client())
            self.scene3d_dock.show()
            self.scene3d_dock.raise_()
        else:
            self.scene3d_dock.hide()

    def _on_scene3d_dock_visibility(self, visible: bool):
        self.scene3d_btn.blockSignals(True)
        self.scene3d_btn.setChecked(visible)
        self.scene3d_btn.blockSignals(False)

    def _active_client(self) -> Optional[OpcUaClient]:
        """Return the OpcUaClient of the currently selected connection tab."""
        widget = self.tab_widget.currentWidget()
        if isinstance(widget, ConnectionTab):
            return widget.opcua_client
        return None

    def _on_active_tab_changed(self, _index: int):
        if hasattr(self, "scene3d_panel"):
            self.scene3d_panel.set_client(self._active_client())

    def _active_node_picker(self) -> Optional[dict]:
        """Return info about the node currently selected in the active tab."""
        node_id = getattr(self, "_last_selected_node", "")
        if not node_id:
            return None
        return {"node_id": node_id}

    def _on_dash_node_selected(self, node_id: str):
        self._last_selected_node = node_id

    def _on_unsubscribe_requested(self, server_name: str, node_id: str):
        # Find the client for this server
        for url, tab in self._tabs.items():
            if tab.server_name == server_name:
                import asyncio
                asyncio.ensure_future(tab.opcua_client.unsubscribe_node(node_id))
                self.subs_panel.remove_item(server_name, node_id)
                break

    def _on_clear_subscriptions(self):
        import asyncio
        for url, tab in self._tabs.items():
            # We can just unsubscribe all from the panel's list for this server
            for (s_name, n_id) in list(self.subs_panel._items.keys()):
                if s_name == tab.server_name:
                    asyncio.ensure_future(tab.opcua_client.unsubscribe_node(n_id))
                    self.subs_panel.remove_item(s_name, n_id)

    def _on_runner_dock_visibility(self, visible: bool):
        """Keep toolbar button in sync when dock is closed via its X button."""
        self.script_runner_btn.blockSignals(True)
        self.script_runner_btn.setChecked(visible)
        self.script_runner_btn.blockSignals(False)

    def _on_settings(self):
        """Show settings dialog."""
        dialog = SettingsDialog(self._settings, self)
        dialog.wipe_all_requested.connect(self._on_wipe_all)
        if dialog.exec():
            self._settings = dialog.get_settings()
            self._save_settings()
            theme_manager.apply_theme(self._settings.get("theme", "system"))
            self.statusBar().showMessage("Settings saved")

    def _on_export_config(self):
        """Export all settings, servers, and favorites to a single JSON file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Configuration", "", "JSON Files (*.json)"
        )
        if not file_path:
            return

        try:
            from app.widgets.favorites_panel import FAVORITES_FILE
            
            data = {"settings": self._settings, "servers": [], "favorites": []}
            
            # Get servers
            data["servers"] = [s.to_dict() for s in self.server_panel.get_all_servers()]
            
            # Get favorites directly from the panel's memory so any upgraded or unsaved favorites are included
            data["favorites"] = [card.fav_item.to_dict() for card in self.favorites_panel._cards]
                    
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)
                
            self.statusBar().showMessage(f"Configuration exported to {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export configuration:\n{e}")

    def _on_import_config(self):
        """Import settings, servers, and favorites from a single JSON file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Configuration", "", "JSON Files (*.json)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                
            # Wipe current UI state
            self.server_panel.clear_servers()
            self.favorites_panel.clear_all()
            
            # Load settings
            if "settings" in data:
                self._settings = data["settings"]
                self._save_settings()
                if "theme" in self._settings:
                    theme_manager.apply_theme(self._settings["theme"])
            
            # Load servers
            if "servers" in data:
                for s_dict in data["servers"]:
                    self.server_panel.add_server(ServerInfo.from_dict(s_dict))
                self._save_servers()
                
            # Load favorites
            if "favorites" in data:
                from app.widgets.favorites_panel import FAVORITES_FILE
                with open(FAVORITES_FILE, "w") as f:
                    json.dump(data["favorites"], f)
                # Need to refresh favorites panel directly
                for item_data in data["favorites"]:
                    from app.models import FavoriteItem
                    self.favorites_panel._add_card(FavoriteItem.from_dict(item_data))
                    
            self.statusBar().showMessage(f"Configuration imported from {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import configuration:\n{e}")

    def _on_wipe_all(self):
        """Wipe all user data."""
        from app.widgets.favorites_panel import FAVORITES_FILE
        
        # Disconnect all
        for url in list(self._tabs.keys()):
            self._on_disconnect_url(url)
            
        self.server_panel.clear_servers()
        self.favorites_panel.clear_all()
        self._settings = {}
        
        # Delete files
        for f in [SERVERS_FILE, SETTINGS_FILE, FAVORITES_FILE]:
            if os.path.exists(f):
                os.remove(f)
                
        # Revert to default theme (System)
        self._settings = {"theme": "system"}
        self._save_settings()
        theme_manager.apply_theme("system")
        self.statusBar().showMessage("All data has been wiped.")

    def _on_favorite_clicked(self, item: FavoriteItem):
        """Single click on a favorite — load / navigate only (never executes)."""
        if item.node_type == NodeType.SCRIPT:
            self.script_runner_btn.setChecked(True)
            self._toggle_script_runner(True)
            self.script_runner_panel.load_script(item.node_id, item.input_args, item.script_content)
            return

        if item.node_type == NodeType.FLOW:
            self.statusBar().showMessage(
                f"Flow '{item.display_name}' — right-click → Run Flow to execute, or Edit Flow to change it."
            )
            return

        asyncio.ensure_future(self._activate_favorite(item, execute=False))

    def _on_favorite_execute(self, item: FavoriteItem):
        """Double click / right-click Run — load and then execute the favorite."""
        if item.node_type == NodeType.SCRIPT:
            self.script_runner_btn.setChecked(True)
            self._toggle_script_runner(True)
            success = self.script_runner_panel.load_script(item.node_id, item.input_args, item.script_content)
            if success:
                self.script_runner_panel._on_run()
            return

        if item.node_type == NodeType.WRITE:
            asyncio.ensure_future(self._run_write_favorite(item))
            return

        if item.node_type == NodeType.FLOW:
            asyncio.ensure_future(self._run_flow(item))
            return

        asyncio.ensure_future(self._activate_favorite(item, execute=True))

    async def _activate_favorite(self, item: FavoriteItem, execute: bool = False):
        """Ensure server connected and then load (and optionally call) a node."""
        # 1. Find which tab to use
        tab = None
        if item.server_url and item.server_url in self._tabs:
            tab = self._tabs[item.server_url]
        elif item.server_url:
            # Not connected yet — try to auto-connect
            server_info = next(
                (s for s in self.server_panel.get_all_servers() if s.url == item.server_url),
                None
            )
            if server_info:
                self.statusBar().showMessage(f"Auto-connecting to {server_info.name}…")
                await self._connect_server(server_info)
                tab = self._tabs.get(item.server_url)
            else:
                self.statusBar().showMessage(
                    f"⚠️  Server {item.server_url} not found in server list."
                )

        # Fallback: use currently active tab
        if tab is None:
            idx = self.tab_widget.currentIndex()
            if idx >= 0:
                tab = self.tab_widget.widget(idx)

        if tab is None:
            self.statusBar().showMessage(
                "⚠️  Connect to a server first, or add it to the server list."
            )
            return

        # Switch to the tab
        idx = self.tab_widget.indexOf(tab)
        if idx >= 0:
            self.tab_widget.setCurrentIndex(idx)

        # Re-resolve the node id via its browse path so the favorite keeps
        # working after a server restart reassigned numeric node ids.
        item.node_id = await self._resolve_node_for(
            tab, item.node_id, item.browse_path, item.id
        )

        # 2. Load node info
        try:
            info = await tab.opcua_client.read_node_attributes(
                item.node_id, tab.server_name
            )
            tab.node_info.update_node(info)
        except Exception:
            pass

        if item.node_type == NodeType.METHOD:
            # 3. Load method arguments from server
            try:
                input_args, output_args = await tab.opcua_client.get_method_arguments(
                    item.node_id
                )
                parent_id = await tab.opcua_client.get_parent_node_id(item.node_id)
            except Exception:
                input_args, output_args, parent_id = [], [], None

            if parent_id:
                display = item.display_name or item.node_id
                tab.node_info.set_method(
                    item.node_id, display, parent_id, input_args, output_args
                )

            # 4. Restore saved args
            if item.input_args:
                tab.node_info.call_method_tab.populate_saved_args(item.input_args)

            # 5. Call the method only when explicitly requested.
            if execute:
                tab.node_info.call_method_tab._on_call()


    async def _add_favorite_with_path(self, tab, url, server_name, node_id, name, ntype, args):
        """Capture a stable browse path before saving an address-space favorite.

        The browse path lets the favorite be re-resolved after a server restart
        reassigns numeric node ids.
        """
        browse_path = []
        if node_id and ntype in (NodeType.METHOD, NodeType.VARIABLE, NodeType.WRITE):
            try:
                browse_path = await tab.opcua_client.get_browse_path(node_id)
            except Exception:
                browse_path = []
        self.favorites_panel.add_favorite(
            node_id, name, ntype, url, server_name, args, browse_path
        )

    async def _resolve_node_for(self, tab, node_id: str, browse_path: list,
                                item_id: str = "") -> str:
        """Resolve the current node id for a favorite/step.

        When a browse path is available it is walked from Root to find the node
        even if its numeric id changed since the favorite was saved. The stored
        favorite is updated with the new id so subsequent calls stay fast.
        """
        resolved = node_id
        if browse_path:
            try:
                rid = await tab.opcua_client.resolve_browse_path(browse_path)
            except Exception:
                rid = None
            if rid:
                resolved = rid
                if item_id and rid != node_id:
                    self.favorites_panel.update_browse_path(item_id, browse_path, rid)
        return resolved

    async def _ensure_tab(self, server_url: str):
        """Return a connected ConnectionTab for the given server URL.

        Auto-connects using the saved server list when needed, falling back to
        the currently active tab if the URL is unknown.
        """
        if server_url and server_url in self._tabs:
            return self._tabs[server_url]

        if server_url:
            server_info = next(
                (s for s in self.server_panel.get_all_servers() if s.url == server_url),
                None,
            )
            if server_info:
                self.statusBar().showMessage(f"Auto-connecting to {server_info.name}…")
                await self._connect_server(server_info)
                tab = self._tabs.get(server_url)
                if tab is not None:
                    return tab

        idx = self.tab_widget.currentIndex()
        if idx >= 0:
            return self.tab_widget.widget(idx)
        return None

    @staticmethod
    def _convert_write_value(raw: str, data_type: str):
        """Convert a string value to the proper Python type for an OPC UA write."""
        converters = {
            "String": str,
            "Boolean": lambda v: v.strip().lower() in ("true", "1", "yes"),
            "Int16": int, "Int32": int, "Int64": int,
            "UInt16": int, "UInt32": int, "UInt64": int,
            "Float": float, "Double": float,
            "Byte": int,
            "ByteString": lambda v: bytes(v, "utf-8"),
        }
        return converters.get(data_type, str)(raw)

    async def _run_write_favorite(self, item: FavoriteItem):
        """Execute a standalone 'set variable' favorite."""
        await self._run_write_step({
            "node_id": item.node_id,
            "server_url": item.server_url,
            "write_value": item.write_value,
            "write_data_type": item.write_data_type,
            "browse_path": item.browse_path,
            "display_name": item.display_name,
        })

    async def _run_write_step(self, step: dict):
        """Write a value to a node as part of a flow / favorite."""
        tab = await self._ensure_tab(step.get("server_url", ""))
        if tab is None:
            raise RuntimeError("No server connection available for set-value step")

        node_id = await self._resolve_node_for(
            tab, step["node_id"], step.get("browse_path", [])
        )
        data_type = step.get("write_data_type") or "String"
        value = self._convert_write_value(step.get("write_value", ""), data_type)
        ok = await tab.opcua_client.write_value(
            node_id, value, data_type, tab.server_name
        )
        if not ok:
            raise RuntimeError(f"Write to {node_id} failed")
        self.statusBar().showMessage(
            f"✅ Set {step.get('display_name') or node_id} = {step.get('write_value', '')}"
        )

    async def _run_method_step(self, step: dict):
        """Call a method as part of a flow, showing it in the UI and awaiting it."""
        fav = FavoriteItem(
            display_name=step.get("display_name", ""),
            node_id=step["node_id"],
            node_type=NodeType.METHOD,
            server_url=step.get("server_url", ""),
            server_name=step.get("server_name", ""),
            input_args=step.get("input_args", []),
            browse_path=step.get("browse_path", []),
        )
        # Load the method into the UI (no call yet). _activate_favorite resolves
        # the node via its browse path so a restarted server still works.
        await self._activate_favorite(fav, execute=False)

        tab = self._tabs.get(step.get("server_url", ""))
        if tab is None:
            idx = self.tab_widget.currentIndex()
            tab = self.tab_widget.widget(idx) if idx >= 0 else None
        if tab is None:
            raise RuntimeError("No server connection available for method step")

        cmt = tab.node_info.call_method_tab
        cmt._on_call()
        if cmt._call_task is not None:
            await cmt._call_task

    async def _run_script_step(self, step: dict):
        """Run a script step and wait for the subprocess to finish."""
        self.script_runner_btn.setChecked(True)
        self._toggle_script_runner(True)
        panel = self.script_runner_panel
        ok = panel.load_script(
            step["node_id"], step.get("input_args", []), step.get("script_content", "")
        )
        if not ok:
            raise RuntimeError(f"Could not load script {step.get('node_id')}")

        loop = asyncio.get_event_loop()
        fut = loop.create_future()

        def _resolver(code, status, _f=fut):
            if not _f.done():
                _f.set_result(code)

        panel._on_run()
        if panel._process is not None:
            panel._process.finished.connect(_resolver)
            exit_code = await fut
            if exit_code != 0:
                raise RuntimeError(f"Script exited with code {exit_code}")

    async def _run_flow(self, item: FavoriteItem):
        """Execute every step of a flow sequentially, stopping on the first error."""
        steps = item.flow_steps or []
        total = len(steps)
        self.statusBar().showMessage(f"▶ Running flow '{item.display_name}' ({total} steps)…")

        for idx, step in enumerate(steps, 1):
            kind = step.get("kind")
            label = step.get("display_name") or kind
            self.statusBar().showMessage(
                f"Flow '{item.display_name}': step {idx}/{total} — {label}"
            )
            try:
                if kind == "wait":
                    await asyncio.sleep(float(step.get("wait_seconds", 0) or 0))
                elif kind == "script":
                    await self._run_script_step(step)
                elif kind == "method":
                    await self._run_method_step(step)
                elif kind == "write":
                    await self._run_write_step(step)
                else:
                    logger.warning(f"Unknown flow step kind: {kind}")
            except Exception as exc:
                self.statusBar().showMessage(
                    f"❌ Flow '{item.display_name}' failed at step {idx}/{total} ({label}): {exc}"
                )
                logger.error(f"Flow '{item.display_name}' step {idx} failed: {exc}")
                return

        self.statusBar().showMessage(
            f"✅ Flow '{item.display_name}' completed ({total} steps)."
        )


    def _on_error(self, operation: str, message: str):
        """Handle OPC UA errors."""
        self.statusBar().showMessage(f"Error in {operation}: {message}")
        logger.error(f"OPC UA Error - {operation}: {message}")

    # ---- Persistence ----

    def _save_servers(self):
        """Save server list to JSON file."""
        servers = self.server_panel.get_all_servers()
        data = [s.to_dict() for s in servers]
        try:
            with open(SERVERS_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save servers: {e}")

    def _load_servers(self):
        """Load server list from JSON file."""
        try:
            if os.path.exists(SERVERS_FILE):
                with open(SERVERS_FILE, "r") as f:
                    data = json.load(f)
                for item in data:
                    server = ServerInfo.from_dict(item)
                    self.server_panel.add_server(server)
        except Exception as e:
            logger.error(f"Failed to load servers: {e}")

        # No longer adding default servers automatically.

    def _save_settings(self):
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(self._settings, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    def _load_settings(self):
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r") as f:
                    self._settings = json.load(f)
                if "theme" in self._settings:
                    theme_manager.apply_theme(self._settings["theme"])
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")

    def closeEvent(self, event):
        """Clean up on close."""
        # Disconnect all clients
        for url, client in list(self._clients.items()):
            asyncio.ensure_future(client.disconnect())
        self._save_servers()
        self._save_settings()
        try:
            self.favorites_panel.save()
        except Exception:
            pass
        event.accept()
