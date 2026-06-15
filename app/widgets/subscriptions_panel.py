"""Subscriptions panel for monitoring OPC UA node changes globally."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QHBoxLayout, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal
from app.theme import Colors, theme_manager
from datetime import datetime

class SubscriptionsPanel(QWidget):
    """Global panel showing all actively monitored items across all servers."""

    unsubscribe_requested = pyqtSignal(str, str)  # server_name, node_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._items = {}  # (server_name, node_id) -> row_index
        theme_manager.theme_changed.connect(self.update_theme)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        self.header = QWidget()
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(12, 12, 12, 12)

        self.title = QLabel("📡 Active Subscriptions")
        header_layout.addWidget(self.title)
        
        header_layout.addStretch()
        
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setStyleSheet("padding: 4px 10px; font-size: 12px;")
        header_layout.addWidget(self.clear_btn)
        
        layout.addWidget(self.header)

        # Table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Server", "Node Name", "Value", "Last Update", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setColumnWidth(0, 100)
        self.table.setColumnWidth(1, 150)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(4, 80)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)

        layout.addWidget(self.table)
        self.update_theme()

    def update_theme(self):
        self.header.setStyleSheet(
            f"background-color: {Colors.BG_DARK}; border-bottom: 1px solid {Colors.BORDER};"
        )
        self.title.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {Colors.TEXT_PRIMARY}; background: transparent;"
        )
        self.clear_btn.setStyleSheet(
            f"padding: 4px 10px; font-size: 12px; color: {Colors.TEXT_PRIMARY};"
        )
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Colors.BG_CARD};
                color: {Colors.TEXT_PRIMARY};
                alternate-background-color: {Colors.BG_MEDIUM};
                gridline-color: {Colors.BORDER};
            }}
        """)

        for row in range(self.table.rowCount()):
            button = self.table.cellWidget(row, 4)
            if isinstance(button, QPushButton):
                self._style_unsubscribe_button(button)

    def _style_unsubscribe_button(self, button: QPushButton):
        button.setStyleSheet(
            f"background-color: {Colors.ERROR}; color: white; padding: 2px 6px; font-size: 11px;"
        )

    def add_or_update_item(self, server_name: str, node_id: str, node_name: str, value: str):
        key = (server_name, node_id)
        now = datetime.now().strftime("%H:%M:%S")

        if key in self._items:
            row = self._items[key]
            self.table.item(row, 2).setText(str(value))
            self.table.item(row, 3).setText(now)
            
            # Flash row color briefly to indicate update
            for col in range(4):
                item = self.table.item(row, col)
                if item:
                    item.setBackground(Qt.GlobalColor.transparent) # Reset could be done here or use QTimer for flash effect
        else:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._items[key] = row

            srv_item = QTableWidgetItem(server_name)
            srv_item.setFlags(srv_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, srv_item)

            node_item = QTableWidgetItem(node_name)
            node_item.setFlags(node_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            node_item.setToolTip(f"Node ID: {node_id}")
            self.table.setItem(row, 1, node_item)

            val_item = QTableWidgetItem(str(value))
            val_item.setFlags(val_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 2, val_item)

            time_item = QTableWidgetItem(now)
            time_item.setFlags(time_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 3, time_item)

            # Unsubscribe button
            unsub_btn = QPushButton("Remove")
            self._style_unsubscribe_button(unsub_btn)
            unsub_btn.clicked.connect(lambda _, s=server_name, n=node_id: self._on_unsubscribe_clicked(s, n))
            self.table.setCellWidget(row, 4, unsub_btn)

    def remove_item(self, server_name: str, node_id: str):
        key = (server_name, node_id)
        if key in self._items:
            row = self._items[key]
            self.table.removeRow(row)
            del self._items[key]
            # Re-index remaining items
            for k, v in list(self._items.items()):
                if v > row:
                    self._items[k] = v - 1

    def _on_unsubscribe_clicked(self, server_name: str, node_id: str):
        self.unsubscribe_requested.emit(server_name, node_id)
