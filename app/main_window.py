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
    QApplication,
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
        self._load_settings()
        
        # Apply theme from settings before setting up UI
        theme = self._settings.get("theme", "dark")
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

        # Central split view: Servers | Tabs | Favorites
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)

        # Left: Server list
        self.server_panel = ServerPanel()
        self.server_panel.server_connect_requested.connect(self._on_connect_server)
        self.server_panel.server_disconnect_requested.connect(self._on_disconnect_server)
        self.server_panel.server_clicked.connect(self._on_server_clicked)
        self.server_panel.add_server_requested.connect(self._on_add_server)
        self.main_splitter.addWidget(self.server_panel)

        # Center: Tabs (Address spaces)
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.tabCloseRequested.connect(self._on_tab_close)
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

        # Add "+" button for new connection
        self.add_tab_btn = QPushButton("+")
        self.add_tab_btn.setFixedSize(28, 28)
        self.add_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_tab_btn.setToolTip("Add a new server connection")
        self.add_tab_btn.clicked.connect(self._on_add_server)
        self.tab_widget.setCornerWidget(self.add_tab_btn, Qt.Corner.TopRightCorner)

        self.main_splitter.addWidget(self.tab_widget)

        # Right: Favorites panel
        self.favorites_panel = FavoritesPanel()
        self.favorites_panel.favorite_clicked.connect(self._on_favorite_clicked)
        self.main_splitter.addWidget(self.favorites_panel)

        # Far right: Script Runner panel (hidden by default)
        self.script_runner_panel = ScriptRunnerPanel()
        self.script_runner_panel.hide()
        self.script_runner_panel.add_to_favorites.connect(
            lambda path, name, args: self.favorites_panel.add_script_favorite(path, name, args)
        )
        self.main_splitter.addWidget(self.script_runner_panel)

        # Set initial proportions
        self.main_splitter.setSizes([260, 800, 260, 0])
        
        content_layout.addWidget(self.main_splitter)
        main_layout.addWidget(content_widget)

        # Status bar
        self.statusBar().showMessage("Ready — No active connections")

        # Initial style setup
        self.update_theme()

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
                background-color: {Colors.BG_DARK};
                border-bottom: 1px solid {Colors.BORDER};
                padding: 4px 12px;
                spacing: 4px;
            }}
        """)

        self.title_label.setStyleSheet(f"""
            font-size: 14px;
            font-weight: bold;
            color: {Colors.TEXT_PRIMARY};
            background: transparent;
            padding: 0 8px;
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
        discover_btn.setText("🔍 Find Server")
        discover_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        discover_btn.clicked.connect(self._on_discover)
        self.toolbar.addWidget(discover_btn)

        # Refresh
        refresh_btn = QToolButton()
        refresh_btn.setText("🔄 Refresh Connections")
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
        fav_btn = QToolButton()
        fav_btn.setText("⭐ Favorites")
        fav_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        fav_btn.setCheckable(True)
        fav_btn.setChecked(True)
        fav_btn.toggled.connect(self._toggle_favorites)
        self.toolbar.addWidget(fav_btn)

        # Script Runner toggle
        self.script_runner_btn = QToolButton()
        self.script_runner_btn.setText("▶ Script Runner")
        self.script_runner_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.script_runner_btn.setCheckable(True)
        self.script_runner_btn.setChecked(False)
        self.script_runner_btn.toggled.connect(self._toggle_script_runner)
        self.toolbar.addWidget(self.script_runner_btn)

        # Theme Toggle
        self.theme_btn = QToolButton()
        self.theme_btn.setText("☀️ Light Mode" if theme_manager.current_mode == "dark" else "🌙 Dark Mode")
        self.theme_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.theme_btn.clicked.connect(self._toggle_theme)
        self.toolbar.addWidget(self.theme_btn)

        # Settings
        settings_btn = QToolButton()
        settings_btn.setText("⚙️ Settings")
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
        client = OpcUaClient(self)
        client.connection_changed.connect(
            lambda u, s: self.server_panel.update_server_status(u, s)
        )
        client.error_occurred.connect(self._on_error)

        success = await client.connect(
            url,
            security_policy=server_info.security_policy,
            username=server_info.username,
            password=server_info.password,
        )

        if success:
            self._clients[url] = client

            # Create connection tab
            tab = ConnectionTab(server_info.name, url, client)
            tab.disconnect_requested.connect(self._on_disconnect_server)
            tab.add_to_favorites.connect(
                lambda nid, name, ntype, args: self.favorites_panel.add_favorite(
                    nid, name, ntype, url, server_info.name, args
                )
            )
            self._tabs[url] = tab

            idx = self.tab_widget.addTab(tab, f"● {server_info.name}")
            self.tab_widget.setCurrentIndex(idx)

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

    def _toggle_favorites(self, visible: bool):
        """Toggle favorites panel visibility."""
        self.favorites_panel.setVisible(visible)

    def _toggle_script_runner(self, visible: bool):
        """Toggle Script Runner panel visibility."""
        self.script_runner_panel.setVisible(visible)
        if visible:
            sizes = self.main_splitter.sizes()
            # Give script runner 320px, reduce center tab width accordingly
            total = sum(sizes)
            runner_width = 320
            sizes[-1] = runner_width
            if sizes[1] > runner_width:
                sizes[1] -= runner_width
            self.main_splitter.setSizes(sizes)
        else:
            sizes = self.main_splitter.sizes()
            sizes[1] += sizes[-1]
            sizes[-1] = 0
            self.main_splitter.setSizes(sizes)

    def _on_settings(self):
        """Show settings dialog."""
        dialog = SettingsDialog(self._settings, self)
        if dialog.exec():
            self._settings = dialog.get_settings()
            self._save_settings()
            self.statusBar().showMessage("Settings saved")

    def _on_favorite_clicked(self, item: FavoriteItem):
        """Navigate to a favorited node in its server's tree or load a script."""
        if item.node_type == NodeType.SCRIPT:
            self.script_runner_btn.setChecked(True)
            self._toggle_script_runner(True)
            self.script_runner_panel.load_script(item.node_id, item.input_args)
            self.script_runner_panel._on_run()
            return

        async def load_and_populate(tab):
            await tab._load_node_info(item.node_id)
            if item.node_type == NodeType.METHOD:
                if item.input_args:
                    tab.node_info.call_method_tab.populate_saved_args(item.input_args)
                tab.node_info.call_method_tab._on_call()

        # Find the tab for this server if it matches
        if item.server_url and item.server_url in self._tabs:
            tab = self._tabs[item.server_url]
            idx = self.tab_widget.indexOf(tab)
            if idx >= 0:
                self.tab_widget.setCurrentIndex(idx)
                asyncio.ensure_future(load_and_populate(tab))
        else:
            # Fallback: try active tab
            idx = self.tab_widget.currentIndex()
            if idx >= 0:
                tab = self.tab_widget.widget(idx)
                asyncio.ensure_future(load_and_populate(tab))

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

    def _toggle_theme(self):
        """Toggle between light and dark themes."""
        new_theme = "light" if theme_manager.current_mode == "dark" else "dark"
        theme_manager.apply_theme(new_theme)
        
        # Save preference
        self._settings["theme"] = new_theme
        self._save_settings()

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
        event.accept()
