"""Connection tab widget — one per connected server, showing address space and node details."""

import asyncio
from typing import Optional

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSplitter, QFrame,
)

from app.models import NodeInfo, NodeType, MethodArgument, ConnectionStatus
from app.opcua_client import OpcUaClient
from app.theme import Colors
from app.widgets.address_tree import AddressTreeWidget
from app.widgets.node_info import NodeInfoWidget


class ConnectionTab(QWidget):
    """A tab representing an active connection to an OPC UA server."""

    disconnect_requested = pyqtSignal(str)  # server url
    add_to_favorites = pyqtSignal(str, str, NodeType, list)  # node_id, name, type, args

    def __init__(
        self, server_name: str, server_url: str,
        opcua_client: OpcUaClient,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.server_name = server_name
        self.server_url = server_url
        self.opcua_client = opcua_client
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Container frame
        container = QFrame()
        container.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_DARK};
                border: 1px solid {Colors.BORDER};
                border-radius: 12px;
            }}
        """)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(14, 14, 14, 14)
        container_layout.setSpacing(10)

        # Header
        header_layout = QHBoxLayout()

        # Server info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        self.title_label = QLabel(self.server_name)
        self.title_label.setStyleSheet(f"""
            font-size: 16px;
            font-weight: bold;
            color: {Colors.TEXT_PRIMARY};
            background: transparent;
        """)
        info_layout.addWidget(self.title_label)

        self.url_label = QLabel(self.server_url)
        self.url_label.setStyleSheet(f"""
            font-size: 11px;
            color: {Colors.TEXT_MUTED};
            background: transparent;
        """)
        info_layout.addWidget(self.url_label)

        header_layout.addLayout(info_layout)
        header_layout.addStretch()

        # Status badge
        self.status_badge = QLabel("● Connected")
        self.status_badge.setStyleSheet(f"""
            color: {Colors.SUCCESS};
            font-size: 12px;
            font-weight: bold;
            background: transparent;
            padding: 4px 8px;
        """)
        header_layout.addWidget(self.status_badge)

        # Disconnect button
        self.disconnect_btn = QPushButton("⚡ Disconnect")
        self.disconnect_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ERROR_BG};
                color: {Colors.ERROR};
                border: 1px solid {Colors.ERROR};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {Colors.ERROR};
                color: white;
            }}
        """)
        self.disconnect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.disconnect_btn.clicked.connect(
            lambda: self.disconnect_requested.emit(self.server_url)
        )
        header_layout.addWidget(self.disconnect_btn)

        # More button
        self.more_btn = QPushButton("···")
        self.more_btn.setFixedSize(32, 32)
        self.more_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
                color: {Colors.TEXT_SECONDARY};
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {Colors.BG_HOVER};
                color: {Colors.TEXT_PRIMARY};
            }}
        """)
        header_layout.addWidget(self.more_btn)

        container_layout.addLayout(header_layout)

        # Content splitter: Address Space | Node Details
        self.content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.content_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: transparent;
                width: 6px;
            }
        """)

        # Left: Address tree
        self.address_tree = AddressTreeWidget()
        self.address_tree.set_client(self.opcua_client)
        self.content_splitter.addWidget(self.address_tree)

        # Right: Node info
        self.node_info = NodeInfoWidget()
        self.node_info.set_client(self.opcua_client, self.server_name)
        self.content_splitter.addWidget(self.node_info)

        # Set proportions (40% tree, 60% details)
        self.content_splitter.setSizes([400, 600])

        container_layout.addWidget(self.content_splitter, 1)

        layout.addWidget(container)

    def _connect_signals(self):
        self.address_tree.node_selected.connect(self._on_node_selected)
        self.address_tree.node_double_clicked.connect(self._on_node_double_clicked)
        self.node_info.add_to_favorites.connect(self.add_to_favorites.emit)

    def _on_node_selected(self, node_id: str):
        """Load node info when a node is clicked in the tree."""
        asyncio.ensure_future(self._load_node_info(node_id))

    def _on_node_double_clicked(self, node_id: str, node_type: NodeType, display_name: str = ""):
        """Handle double-click — load method args if it's a method."""
        if node_type == NodeType.METHOD:
            asyncio.ensure_future(self._load_method(node_id, display_name))

    async def _load_node_info(self, node_id: str):
        """Load and display node information."""
        try:
            info = await self.opcua_client.read_node_attributes(
                node_id, self.server_name
            )
            self.node_info.update_node(info)

            # If it's a method, also load method arguments
            if info.node_class == NodeType.METHOD:
                await self._load_method(node_id, info.display_name)
        except Exception as e:
            print(f"Error loading node info: {e}")

    async def _load_method(self, method_node_id: str, display_name: str = ""):
        """Load method arguments and set up the call interface."""
        try:
            input_args, output_args = await self.opcua_client.get_method_arguments(
                method_node_id
            )
            parent_id = await self.opcua_client.get_parent_node_id(method_node_id)
            if parent_id:
                if not display_name:
                    display_name = method_node_id.split(".")[-1] if "." in method_node_id else method_node_id
                self.node_info.set_method(method_node_id, display_name, parent_id, input_args, output_args)
        except Exception as e:
            print(f"Error loading method: {e}")

    async def load_address_space(self):
        """Load the root of the address space tree."""
        await self.address_tree.load_root()

    def update_connection_status(self, status: ConnectionStatus):
        """Update the displayed connection status."""
        if status == ConnectionStatus.CONNECTED:
            self.status_badge.setText("● Connected")
            self.status_badge.setStyleSheet(f"""
                color: {Colors.SUCCESS};
                font-size: 12px;
                font-weight: bold;
                background: transparent;
                padding: 4px 8px;
            """)
        elif status == ConnectionStatus.DISCONNECTED:
            self.status_badge.setText("● Disconnected")
            self.status_badge.setStyleSheet(f"""
                color: {Colors.TEXT_MUTED};
                font-size: 12px;
                font-weight: bold;
                background: transparent;
                padding: 4px 8px;
            """)
        elif status == ConnectionStatus.ERROR:
            self.status_badge.setText("● Error")
            self.status_badge.setStyleSheet(f"""
                color: {Colors.ERROR};
                font-size: 12px;
                font-weight: bold;
                background: transparent;
                padding: 4px 8px;
            """)
