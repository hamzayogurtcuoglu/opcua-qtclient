"""Server discovery dialog — find OPC UA servers via LDS."""

import asyncio
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QCheckBox, QFrame,
)

from app.opcua_client import OpcUaClient
from app.models import ServerInfo
from app.theme import Colors


class DiscoveryDialog(QDialog):
    """Dialog for discovering OPC UA servers."""

    def __init__(self, parent: Optional[object] = None):
        super().__init__(parent)
        self._results: list[ServerInfo] = []
        self._selected: list[ServerInfo] = []
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Discover Servers")
        self.setMinimumSize(500, 400)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Colors.BG_DARK};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Title
        title = QLabel("🔍 Find Servers")
        title.setStyleSheet(f"""
            font-size: 18px;
            font-weight: bold;
            color: {Colors.TEXT_PRIMARY};
            background: transparent;
        """)
        layout.addWidget(title)

        subtitle = QLabel("Click the button below to scan common local ports (4840-4845) for available OPC UA servers.")
        subtitle.setStyleSheet(f"font-size: 12px; color: {Colors.TEXT_SECONDARY}; background: transparent;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # Scan button
        scan_layout = QHBoxLayout()
        self.find_btn = QPushButton("🔍 Scan Local Servers")
        self.find_btn.setProperty("class", "primary")
        self.find_btn.clicked.connect(self._on_find)
        self.find_btn.setMinimumHeight(36)
        scan_layout.addWidget(self.find_btn)
        scan_layout.addStretch()
        layout.addLayout(scan_layout)

        # Status
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px; background: transparent;")
        layout.addWidget(self.status_label)

        # Results list
        self.results_list = QListWidget()
        self.results_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {Colors.BG_INPUT};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                padding: 4px;
            }}
            QListWidget::item {{
                padding: 8px;
                border-radius: 4px;
                margin: 2px;
            }}
            QListWidget::item:selected {{
                background-color: {Colors.ACCENT};
            }}
        """)
        layout.addWidget(self.results_list, 1)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumWidth(100)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self.add_btn = QPushButton("Add Selected")
        self.add_btn.setProperty("class", "primary")
        self.add_btn.setMinimumWidth(120)
        self.add_btn.setEnabled(False)
        self.add_btn.clicked.connect(self._on_add)
        btn_layout.addWidget(self.add_btn)

        layout.addLayout(btn_layout)

    def _on_find(self):
        self.status_label.setText("Scanning ports 4840-4845...")
        self.find_btn.setEnabled(False)
        self.results_list.clear()
        self._results.clear()
        asyncio.ensure_future(self._scan_all())

    async def _scan_all(self):
        tasks = []
        for port in range(4840, 4846):
            url = f"opc.tcp://127.0.0.1:{port}"
            tasks.append(self._try_discover(url))
        
        await asyncio.gather(*tasks)

        self.status_label.setText(f"Found {len(self._results)} server(s).")
        self.add_btn.setEnabled(len(self._results) > 0)
        self.find_btn.setEnabled(True)

    async def _try_discover(self, url: str):
        try:
            client = OpcUaClient()
            servers = await client.discover_servers(url)
            if not servers:
                return

            for server in servers:
                name = server.get("name", "Unknown")
                urls = server.get("urls", [])
                
                # if urls is empty, fallback to the discovery url
                if not urls:
                    urls = [url]

                for srv_url in urls:
                    # Fix localhost resolution if returned by server
                    if "localhost" in srv_url:
                        srv_url = srv_url.replace("localhost", "127.0.0.1")
                        
                    # Avoid duplicates
                    if any(r.url == srv_url for r in self._results):
                        continue
                        
                    info = ServerInfo(name=name, url=srv_url)
                    self._results.append(info)

                    item = QListWidgetItem(f"  {name}\n  {srv_url}")
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(Qt.CheckState.Unchecked)
                    self.results_list.addItem(item)
        except Exception:
            pass

    def _on_add(self):
        from PyQt6.QtWidgets import QInputDialog
        self._selected.clear()
        for i in range(self.results_list.count()):
            item = self.results_list.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                if i < len(self._results):
                    server = self._results[i]
                    name, ok = QInputDialog.getText(
                        self, "Name Server", 
                        f"Enter a name for:\n{server.url}",
                        QLineEdit.EchoMode.Normal, server.name
                    )
                    if ok and name.strip():
                        server.name = name.strip()
                    self._selected.append(server)

        if self._selected:
            self.accept()

    def get_selected_servers(self) -> list[ServerInfo]:
        return self._selected
