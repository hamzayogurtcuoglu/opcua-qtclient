"""Address space tree widget for browsing OPC UA nodes."""

import asyncio
from typing import Optional

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor, QFont, QBrush
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QHBoxLayout, QLineEdit, QLabel, QFrame,
)

from app.models import NodeType
from app.theme import Colors


# Unicode icons for node types
NODE_ICONS = {
    NodeType.OBJECT: "📁",
    NodeType.VARIABLE: "🔵",
    NodeType.METHOD: "🟣",
    NodeType.VIEW: "👁",
    NodeType.OBJECT_TYPE: "📂",
    NodeType.VARIABLE_TYPE: "🔷",
    NodeType.REFERENCE_TYPE: "🔗",
    NodeType.DATA_TYPE: "📊",
    NodeType.UNKNOWN: "❓",
}

NODE_COLORS = {
    NodeType.OBJECT: Colors.NODE_OBJECT,
    NodeType.VARIABLE: Colors.NODE_VARIABLE,
    NodeType.METHOD: Colors.NODE_METHOD,
    NodeType.VIEW: Colors.NODE_VIEW,
}


class AddressTreeWidget(QWidget):
    """Tree widget for browsing the OPC UA address space."""

    node_selected = pyqtSignal(str)  # node_id
    node_double_clicked = pyqtSignal(str, NodeType)  # node_id, node_type

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._opcua_client = None
        self._loaded_nodes: set[str] = set()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Header
        header = QLabel("Address Space")
        header.setStyleSheet(f"""
            font-size: 13px;
            font-weight: bold;
            color: {Colors.TEXT_PRIMARY};
            background: transparent;
            padding: 4px 0px;
        """)
        layout.addWidget(header)

        # Search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search nodes...")
        self.search_input.textChanged.connect(self._filter_nodes)
        layout.addWidget(self.search_input)

        # Tree
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(20)
        self.tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {Colors.BG_DARK};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                padding: 4px;
            }}
        """)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tree.itemExpanded.connect(self._on_item_expanded)
        layout.addWidget(self.tree, 1)

    def set_client(self, client):
        """Set the OPC UA client instance."""
        self._opcua_client = client

    def clear(self):
        """Clear the tree."""
        self.tree.clear()
        self._loaded_nodes.clear()

    async def load_root(self):
        """Load the root node and its immediate children."""
        self.tree.clear()
        self._loaded_nodes.clear()

        if not self._opcua_client:
            return

        # Add Root node
        root_item = QTreeWidgetItem(self.tree, ["Root"])
        root_item.setData(0, Qt.ItemDataRole.UserRole, "i=84")
        root_item.setData(0, Qt.ItemDataRole.UserRole + 1, NodeType.OBJECT)
        self._style_item(root_item, NodeType.OBJECT)

        # Load children of Objects folder
        await self._load_children(root_item, "i=84")
        root_item.setExpanded(True)

    async def _load_children(self, parent_item: QTreeWidgetItem, node_id: str):
        """Lazily load children of a tree node."""
        if node_id in self._loaded_nodes:
            return

        if not self._opcua_client:
            return

        self._loaded_nodes.add(node_id)

        children = await self._opcua_client.browse_node(node_id)
        for child in children:
            child_item = QTreeWidgetItem(parent_item)
            child_item.setText(0, f"  {child['display_name']}")
            child_item.setData(0, Qt.ItemDataRole.UserRole, child["node_id"])
            child_item.setData(0, Qt.ItemDataRole.UserRole + 1, child["node_class"])

            self._style_item(child_item, child["node_class"])

            # Add placeholder for expandable nodes (objects, folders)
            if child["node_class"] in (NodeType.OBJECT, NodeType.OBJECT_TYPE, NodeType.VIEW):
                placeholder = QTreeWidgetItem(child_item, ["Loading..."])
                placeholder.setForeground(0, QBrush(QColor(Colors.TEXT_MUTED)))

    def _style_item(self, item: QTreeWidgetItem, node_type: NodeType):
        """Apply icon and color styling to a tree item."""
        icon = NODE_ICONS.get(node_type, "❓")
        current_text = item.text(0).strip()
        item.setText(0, f"{icon}  {current_text}")

        color = NODE_COLORS.get(node_type, Colors.TEXT_PRIMARY)
        item.setForeground(0, QBrush(QColor(color)))

        font = item.font(0)
        font.setPointSize(11)
        if node_type == NodeType.METHOD:
            font.setItalic(True)
        item.setFont(0, font)

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        node_id = item.data(0, Qt.ItemDataRole.UserRole)
        if node_id:
            self.node_selected.emit(node_id)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        node_id = item.data(0, Qt.ItemDataRole.UserRole)
        node_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if node_id and node_type:
            self.node_double_clicked.emit(node_id, node_type)

    def _on_item_expanded(self, item: QTreeWidgetItem):
        """Load children when a node is expanded (lazy loading)."""
        node_id = item.data(0, Qt.ItemDataRole.UserRole)
        if node_id and node_id not in self._loaded_nodes:
            # Remove placeholder
            for i in range(item.childCount()):
                child = item.child(i)
                if child and child.text(0) == "Loading...":
                    item.removeChild(child)
                    break

            asyncio.ensure_future(self._load_children(item, node_id))

    def _filter_nodes(self, text: str):
        """Filter tree items based on search text."""
        text = text.lower()
        root = self.tree.invisibleRootItem()
        self._filter_recursive(root, text)

    def _filter_recursive(self, item: QTreeWidgetItem, text: str) -> bool:
        """Recursively filter tree items. Returns True if item or any child matches."""
        if not text:
            # Show all
            for i in range(item.childCount()):
                child = item.child(i)
                if child:
                    child.setHidden(False)
                    self._filter_recursive(child, text)
            return True

        any_child_visible = False
        for i in range(item.childCount()):
            child = item.child(i)
            if child:
                child_text = child.text(0).lower()
                child_matches = text in child_text
                descendant_matches = self._filter_recursive(child, text)
                visible = child_matches or descendant_matches
                child.setHidden(not visible)
                if visible:
                    any_child_visible = True

        return any_child_visible
