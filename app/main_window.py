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

        # Central split view: Servers | Tabs
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

        # Add "+" button for new connection
        self.add_tab_btn = QPushButton("+")
        self.add_tab_btn.setFixedSize(28, 28)
        self.add_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_tab_btn.setToolTip("Add a new server connection")
        self.add_tab_btn.clicked.connect(self._on_add_server)
        self.tab_widget.setCornerWidget(self.add_tab_btn, Qt.Corner.TopRightCorner)

        self.main_splitter.addWidget(self.tab_widget)
        self.main_splitter.setSizes([260, 900])

        content_layout.addWidget(self.main_splitter)
        main_layout.addWidget(content_widget)

        # ── Floating Dock: Favorites ──────────────────────────────────────────
        self.favorites_panel = FavoritesPanel()
        self.favorites_panel.favorite_clicked.connect(self._on_favorite_clicked)

        self.fav_dock = QDockWidget("⭐  Favorites", self)
        self.fav_dock.setWidget(self.favorites_panel)
        self.fav_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea |
            Qt.DockWidgetArea.RightDockWidgetArea |
            Qt.DockWidgetArea.NoDockWidgetArea
        )
        self.fav_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.fav_dock.setFloating(True)
        self.fav_dock.resize(280, 500)
        # Position top-right relative to window
        self.fav_dock.move(
            self.x() + self.width() - 310,
            self.y() + 80
        )
        self.fav_dock.hide()
        self.fav_dock.visibilityChanged.connect(self._on_fav_dock_visibility)

        # ── Floating Dock: Script Runner ──────────────────────────────────────
        self.script_runner_panel = ScriptRunnerPanel()
        self.script_runner_panel.add_to_favorites.connect(
            lambda path, name, args: self.favorites_panel.add_script_favorite(path, name, args)
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
        self.fav_btn = QToolButton()
        self.fav_btn.setText("⭐ Favorites")
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

        # Theme Toggle
        self.theme_btn = QToolButton()
        self.theme_btn.setText("☀️ Light Mode" if theme_manager.current_mode == "dark" else "🌙 Dark Mode")
        self.theme_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.theme_btn.clicked.connect(self._toggle_theme)
        self.toolbar.addWidget(self.theme_btn)

        self.toolbar.addSeparator()

        # Import/Export
        import_btn = QToolButton()
        import_btn.setText("📂 Import")
        import_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        import_btn.clicked.connect(self._on_import_config)
        self.toolbar.addWidget(import_btn)

        export_btn = QToolButton()
        export_btn.setText("💾 Export")
        export_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        export_btn.clicked.connect(self._on_export_config)
        self.toolbar.addWidget(export_btn)

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
        """Toggle favorites pop-up dock."""
        if visible:
            self.fav_dock.show()
            self.fav_dock.raise_()
        else:
            self.fav_dock.hide()

    def _on_fav_dock_visibility(self, visible: bool):
        """Keep toolbar button in sync when dock is closed via its X button."""
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
            
            # Get favorites
            if os.path.exists(FAVORITES_FILE):
                with open(FAVORITES_FILE, "r") as f:
                    data["favorites"] = json.load(f)
                    
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
                
        # Revert to default theme
        theme_manager.apply_theme("dark")
        self.statusBar().showMessage("All data has been wiped.")

    def _on_favorite_clicked(self, item: FavoriteItem):
        """Navigate to a favorited node in its server's tree or load a script."""
        if item.node_type == NodeType.SCRIPT:
            self.script_runner_btn.setChecked(True)
            self._toggle_script_runner(True)
            self.script_runner_panel.load_script(item.node_id, item.input_args)
            self.script_runner_panel._on_run()
            return

        asyncio.ensure_future(self._activate_favorite(item))

    async def _activate_favorite(self, item: FavoriteItem):
        """Ensure server connected and then call method / load node."""
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

            # 5. Call the method
            tab.node_info.call_method_tab._on_call()


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
