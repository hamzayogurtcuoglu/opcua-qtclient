"""Server discovery dialog — find OPC UA servers via LDS and TCP probing."""

import asyncio
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QFrame,
)

from app.opcua_client import OpcUaClient
from app.models import ServerInfo
from app.theme import Colors


DEFAULT_SCAN_HOST = "127.0.0.1"
DEFAULT_PORT_SPEC = "1-65535"
SCAN_WORKERS = 256
TCP_CONNECT_TIMEOUT = 0.15
OPCUA_DISCOVERY_TIMEOUT = 2.0


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

        subtitle = QLabel("Scan the selected host and port range for listening OPC UA servers.")
        subtitle.setStyleSheet(f"font-size: 12px; color: {Colors.TEXT_SECONDARY}; background: transparent;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        target_layout = QHBoxLayout()
        target_layout.setSpacing(8)

        self.host_input = QLineEdit(DEFAULT_SCAN_HOST)
        self.host_input.setPlaceholderText("Host")
        target_layout.addWidget(self.host_input, 1)

        self.ports_input = QLineEdit(DEFAULT_PORT_SPEC)
        self.ports_input.setPlaceholderText("Ports, e.g. 4840,4841,4900-5000")
        target_layout.addWidget(self.ports_input, 2)

        layout.addLayout(target_layout)

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
        try:
            ports = self._parse_ports(self.ports_input.text())
        except ValueError as exc:
            self.status_label.setText(str(exc))
            return

        host = self.host_input.text().strip() or DEFAULT_SCAN_HOST
        self.status_label.setText(f"Scanning {host} ports {self.ports_input.text().strip() or DEFAULT_PORT_SPEC}...")
        self.find_btn.setEnabled(False)
        self.results_list.clear()
        self._results.clear()
        asyncio.ensure_future(self._scan_all(host, ports))

    async def _scan_all(self, host: str, ports: list[int]):
        queue: asyncio.Queue[int | None] = asyncio.Queue()
        total = len(ports)
        scanned = 0
        open_ports = 0

        for port in ports:
            queue.put_nowait(port)
        for _ in range(min(SCAN_WORKERS, total)):
            queue.put_nowait(None)

        async def worker():
            nonlocal scanned, open_ports
            while True:
                port = await queue.get()
                if port is None:
                    queue.task_done()
                    return

                try:
                    if await self._is_tcp_open(host, port):
                        open_ports += 1
                        await self._try_discover(f"opc.tcp://{host}:{port}")
                finally:
                    scanned += 1
                    if scanned % 500 == 0 or scanned == total:
                        self.status_label.setText(
                            f"Scanned {scanned}/{total} port(s), {open_ports} open, found {len(self._results)} server(s)..."
                        )
                    queue.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(min(SCAN_WORKERS, total))]
        await queue.join()
        await asyncio.gather(*workers, return_exceptions=True)

        self.status_label.setText(f"Found {len(self._results)} server(s).")
        self.add_btn.setEnabled(len(self._results) > 0)
        self.find_btn.setEnabled(True)

    async def _is_tcp_open(self, host: str, port: int) -> bool:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=TCP_CONNECT_TIMEOUT,
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False

    async def _try_discover(self, url: str):
        try:
            client = OpcUaClient()
            servers = await client.discover_servers(url, timeout=OPCUA_DISCOVERY_TIMEOUT)
            if not servers:
                probe = await client.probe_server(url, timeout=OPCUA_DISCOVERY_TIMEOUT)
                if probe:
                    servers = [probe]
                else:
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

    def _parse_ports(self, text: str) -> list[int]:
        spec = (text or DEFAULT_PORT_SPEC).strip()
        ports: set[int] = set()

        try:
            for part in spec.split(","):
                part = part.strip()
                if not part:
                    continue

                if "-" in part:
                    start_text, end_text = part.split("-", 1)
                    start = int(start_text.strip())
                    end = int(end_text.strip())
                    if start > end:
                        start, end = end, start
                    ports.update(range(start, end + 1))
                else:
                    ports.add(int(part))
        except ValueError as exc:
            raise ValueError("Use ports like 4840,4841 or 4800-4900.") from exc

        ports = {port for port in ports if 1 <= port <= 65535}
        if not ports:
            raise ValueError("Enter at least one valid port between 1 and 65535.")
        return sorted(ports)

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
