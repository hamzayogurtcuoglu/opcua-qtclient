"""Method calling panel — bottom-right panel for calling OPC UA methods."""

import asyncio
from typing import Optional, Any

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QPushButton,
    QComboBox, QTextEdit, QHeaderView, QFrame,
)

from app.models import MethodArgument, NodeType
from app.theme import Colors, theme_manager


class MethodPanel(QWidget):
    """Bottom-right panel for calling OPC UA methods."""

    method_called = pyqtSignal(str, str)  # method_node_id, result
    add_to_favorites_requested = pyqtSignal(str, str, NodeType, list)  # node_id, name, type, args

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._method_node_id: Optional[str] = None
        self._parent_node_id: Optional[str] = None
        self._opcua_client = None
        self._server_name = ""
        self._input_args: list[MethodArgument] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.panel = QFrame()
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(12, 12, 12, 12)
        panel_layout.setSpacing(8)

        # Header
        self.header = QLabel("Method Call")
        panel_layout.addWidget(self.header)

        # Method selector
        method_row = QHBoxLayout()
        self.method_label = QLabel("Method:")
        method_row.addWidget(self.method_label)

        self.method_combo = QComboBox()
        self.method_combo.setMinimumWidth(200)
        self.method_combo.currentTextChanged.connect(self._on_method_changed)
        method_row.addWidget(self.method_combo, 1)

        self.fav_btn = QPushButton("⭐")
        self.fav_btn.setFixedSize(28, 28)
        self.fav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fav_btn.clicked.connect(self._on_favorite)
        method_row.addWidget(self.fav_btn)

        panel_layout.addLayout(method_row)

        # Input Parameters
        self.input_label = QLabel("Input Parameters")
        panel_layout.addWidget(self.input_label)

        self.params_table = QTableWidget(0, 4)
        self.params_table.setHorizontalHeaderLabels(["#", "Name", "Type", "Value"])
        self.params_table.horizontalHeader().setStretchLastSection(True)
        self.params_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed
        )
        self.params_table.setColumnWidth(0, 30)
        self.params_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.params_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.params_table.verticalHeader().setVisible(False)
        self.params_table.verticalHeader().setDefaultSectionSize(36)
        self.params_table.setMinimumHeight(120)
        self.params_table.setMaximumHeight(250)
        panel_layout.addWidget(self.params_table)

        # Buttons
        btn_layout = QHBoxLayout()
        self.call_btn = QPushButton("▶  Call")
        self.call_btn.setProperty("class", "primary")
        self.call_btn.setMinimumWidth(140)
        self.call_btn.setMinimumHeight(34)
        self.call_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.call_btn.clicked.connect(self._on_call)
        btn_layout.addWidget(self.call_btn)

        btn_layout.addStretch()

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self._on_clear)
        btn_layout.addWidget(self.clear_btn)

        panel_layout.addLayout(btn_layout)

        # Output
        self.output_label = QLabel("Output")
        panel_layout.addWidget(self.output_label)

        self.output_display = QTextEdit()
        self.output_display.setReadOnly(True)
        self.output_display.setMaximumHeight(60)
        panel_layout.addWidget(self.output_display)

        layout.addWidget(self.panel)

        self.update_theme()
        theme_manager.theme_changed.connect(self.update_theme)

    def update_theme(self):
        self.panel.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_DARK};
                border: 1px solid {Colors.BORDER};
                border-radius: 12px;
            }}
        """)
        
        self.header.setStyleSheet(f"""
            font-size: 14px;
            font-weight: bold;
            color: {Colors.TEXT_PRIMARY};
            background: transparent;
        """)
        
        self.method_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent;")
        
        self.fav_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                font-size: 16px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {Colors.BG_HOVER};
            }}
        """)
        
        self.input_label.setStyleSheet(f"""
            font-size: 12px;
            font-weight: bold;
            color: {Colors.TEXT_PRIMARY};
            background: transparent;
        """)
        
        self.output_label.setStyleSheet(f"""
            font-size: 12px;
            font-weight: bold;
            color: {Colors.TEXT_PRIMARY};
            background: transparent;
        """)
        
        self.output_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Colors.BG_INPUT};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                padding: 8px;
                font-family: 'Menlo', 'Courier New', 'Courier';
                font-size: 12px;
                color: {Colors.TEXT_PRIMARY};
            }}
        """)

    def set_client(self, client, server_name: str = ""):
        self._opcua_client = client
        self._server_name = server_name

    def set_method(self, method_node_id: str, parent_node_id: str,
                   display_name: str, input_args: list[MethodArgument]):
        """Set the method to call and populate parameters."""
        self._method_node_id = method_node_id
        self._parent_node_id = parent_node_id
        self._input_args = input_args

        # Update combo if not already present
        if self.method_combo.findText(method_node_id) < 0:
            self.method_combo.addItem(method_node_id)
        self.method_combo.setCurrentText(method_node_id)

        self._populate_params(input_args)

    def _populate_params(self, args: list[MethodArgument]):
        self.params_table.setRowCount(len(args))
        for i, arg in enumerate(args):
            num_item = QTableWidgetItem(str(i + 1))
            num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.params_table.setItem(i, 0, num_item)

            name_item = QTableWidgetItem(arg.name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.params_table.setItem(i, 1, name_item)

            type_item = QTableWidgetItem(arg.data_type)
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.params_table.setItem(i, 2, type_item)

            val_item = QTableWidgetItem(str(arg.value or ""))
            self.params_table.setItem(i, 3, val_item)

    def _on_method_changed(self, text: str):
        pass  # Could load args for the selected method

    def _on_call(self):
        if self._method_node_id and self._opcua_client:
            asyncio.ensure_future(self._call_method())

    async def _call_method(self):
        if not self._method_node_id or not self._opcua_client:
            return

        args = []
        for i in range(self.params_table.rowCount()):
            val_item = self.params_table.item(i, 3)
            type_item = self.params_table.item(i, 2)
            if val_item and type_item:
                raw_val = val_item.text()
                data_type = type_item.text()
                try:
                    args.append(self._convert_arg(raw_val, data_type))
                except Exception:
                    args.append(raw_val)

        result = await self._opcua_client.call_method(
            self._parent_node_id, self._method_node_id,
            args, self._server_name
        )

        if result is not None:
            self.output_display.setText(f"OutputArguments: {result}")
        else:
            self.output_display.setText("OutputArguments: ()")

        self.method_called.emit(self._method_node_id, self.output_display.toPlainText())

    def _on_clear(self):
        for i in range(self.params_table.rowCount()):
            item = self.params_table.item(i, 3)
            if item:
                item.setText("")
        self.output_display.clear()

    def _on_favorite(self):
        if self._method_node_id:
            name = self._method_node_id.split(".")[-1] if "." in self._method_node_id else self._method_node_id
            
            # Gather current input args
            saved_args = []
            for i in range(self.params_table.rowCount()):
                val_item = self.params_table.item(i, 3)
                if val_item:
                    saved_args.append(val_item.text())
            
            self.add_to_favorites_requested.emit(
                self._method_node_id, name, NodeType.METHOD, saved_args
            )

    def populate_saved_args(self, args: list):
        """Restore saved arguments into the table."""
        for i, val in enumerate(args):
            if i < self.params_table.rowCount():
                item = self.params_table.item(i, 3)
                if item:
                    item.setText(str(val))

    def _convert_arg(self, raw: str, data_type: str) -> Any:
        converters = {
            "Boolean": lambda v: v.lower() in ("true", "1", "yes"),
            "Int16": int, "Int32": int, "Int64": int,
            "UInt16": int, "UInt32": int, "UInt64": int,
            "Float": float, "Double": float,
            "Byte": int, "String": str,
        }
        converter = converters.get(data_type, str)
        return converter(raw)
