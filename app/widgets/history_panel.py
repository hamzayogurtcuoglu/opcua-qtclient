"""Operation history panel — bottom-left table showing logged operations."""

from typing import Optional

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
)

from app.models import HistoryEntry, OperationResult
from app.theme import Colors

MAX_HISTORY = 1000


class HistoryPanel(QWidget):
    """Bottom panel showing operation history."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._entries: list[HistoryEntry] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        panel = QFrame()
        panel.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_DARK};
                border: 1px solid {Colors.BORDER};
                border-radius: 12px;
            }}
        """)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 12, 12, 12)
        panel_layout.setSpacing(8)

        # Header
        header = QLabel("Operation History")
        header.setStyleSheet(f"""
            font-size: 14px;
            font-weight: bold;
            color: {Colors.TEXT_PRIMARY};
            background: transparent;
        """)
        panel_layout.addWidget(header)

        # Table
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Time", "Server", "NodeId", "Operation", "Result", "Value / Output"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed
        )
        self.table.setColumnWidth(0, 70)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Fixed
        )
        self.table.setColumnWidth(1, 100)
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Fixed
        )
        self.table.setColumnWidth(3, 70)
        self.table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Fixed
        )
        self.table.setColumnWidth(4, 70)

        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                alternate-background-color: {Colors.BG_MEDIUM};
            }}
        """)

        panel_layout.addWidget(self.table, 1)

        layout.addWidget(panel)

    def add_entry(self, entry: HistoryEntry):
        """Add a new operation entry to the history."""
        self._entries.append(entry)

        # Enforce max history
        if len(self._entries) > MAX_HISTORY:
            self._entries.pop(0)
            self.table.removeRow(0)

        row = self.table.rowCount()
        self.table.insertRow(row)

        # Time
        time_item = QTableWidgetItem(entry.time_str)
        time_item.setForeground(QBrush(QColor(Colors.TEXT_SECONDARY)))
        self.table.setItem(row, 0, time_item)

        # Server
        server_item = QTableWidgetItem(entry.server_name)
        self.table.setItem(row, 1, server_item)

        # NodeId
        nodeid_item = QTableWidgetItem(entry.node_id)
        nodeid_item.setForeground(QBrush(QColor(Colors.TEXT_SECONDARY)))
        self.table.setItem(row, 2, nodeid_item)

        # Operation
        op_item = QTableWidgetItem(entry.operation.value)
        self.table.setItem(row, 3, op_item)

        # Result badge
        result_item = QTableWidgetItem(entry.result.value)
        if entry.result == OperationResult.SUCCESS:
            result_item.setForeground(QBrush(QColor(Colors.SUCCESS)))
            result_item.setBackground(QBrush(QColor(Colors.SUCCESS_BG)))
        else:
            result_item.setForeground(QBrush(QColor(Colors.ERROR)))
            result_item.setBackground(QBrush(QColor(Colors.ERROR_BG)))
        self.table.setItem(row, 4, result_item)

        # Value
        val_item = QTableWidgetItem(entry.value)
        self.table.setItem(row, 5, val_item)

        # Auto-scroll to latest
        self.table.scrollToBottom()

    def clear_history(self):
        """Clear all history entries."""
        self._entries.clear()
        self.table.setRowCount(0)
