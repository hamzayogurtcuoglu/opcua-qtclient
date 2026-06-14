"""Node information widget — shows Properties, Value, Write, Call Method tabs."""

import asyncio
from typing import Optional, Any

from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QTableWidget, QTableWidgetItem, QPushButton, QLineEdit,
    QComboBox, QTextEdit, QFrame, QHeaderView, QSpinBox,
    QFormLayout, QSizePolicy, QCheckBox
)

from app.models import NodeInfo, NodeType, MethodArgument
from app.theme import Colors, theme_manager


class PropertiesTab(QWidget):
    """Shows node attributes in a read-only table."""

    add_to_favorites = pyqtSignal(str, str, NodeType)  # node_id, display_name, node_type

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_node: Optional[NodeInfo] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # Node Information section
        self.info_label = QLabel("Node Information")
        layout.addWidget(self.info_label)

        self.info_table = QTableWidget(6, 2)
        self.info_table.setHorizontalHeaderLabels(["Property", "Value"])
        self.info_table.horizontalHeader().setStretchLastSection(True)
        self.info_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.info_table.verticalHeader().setVisible(False)
        self.info_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.info_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.info_table.setShowGrid(False)
        self.info_table.setAlternatingRowColors(True)

        properties = ["NodeId", "BrowseName", "DisplayName", "NodeClass", "Description", "WriteMask", "UserWriteMask"]
        self.info_table.setRowCount(len(properties))
        for i, prop in enumerate(properties):
            item = QTableWidgetItem(prop)
            item.setForeground(Qt.GlobalColor.white)
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            self.info_table.setItem(i, 0, item)
            self.info_table.setItem(i, 1, QTableWidgetItem(""))

        layout.addWidget(self.info_table)

        # Attributes section
        self.attr_label = QLabel("Attributes")
        layout.addWidget(self.attr_label)

        self.attr_table = QTableWidget(5, 2)
        self.attr_table.setHorizontalHeaderLabels(["Attribute", "Value"])
        self.attr_table.horizontalHeader().setStretchLastSection(True)
        self.attr_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.attr_table.verticalHeader().setVisible(False)
        self.attr_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.attr_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.attr_table.setShowGrid(False)
        self.attr_table.setAlternatingRowColors(True)

        attrs = ["Executable", "UserExecutable", "EventNotifier", "WriteMask", "UserWriteMask"]
        self.attr_table.setRowCount(len(attrs))
        for i, attr in enumerate(attrs):
            item = QTableWidgetItem(attr)
            item.setForeground(Qt.GlobalColor.white)
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            self.attr_table.setItem(i, 0, item)
            self.attr_table.setItem(i, 1, QTableWidgetItem(""))

        layout.addWidget(self.attr_table)

        # Add to favorites button
        self.fav_btn = QPushButton("+ Add to Favorites")
        self.fav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fav_btn.clicked.connect(self._on_add_favorite)
        layout.addWidget(self.fav_btn)

        layout.addStretch()

        self.update_theme()
        theme_manager.theme_changed.connect(self.update_theme)

    def update_theme(self):
        self.info_label.setStyleSheet(f"""
            font-size: 13px;
            font-weight: bold;
            color: {Colors.TEXT_PRIMARY};
            background: transparent;
            border: none;
        """)
        
        self.info_table.setStyleSheet(f"""
            QTableWidget {{
                alternate-background-color: {Colors.BG_MEDIUM};
            }}
        """)
        
        self.attr_label.setStyleSheet(f"""
            font-size: 13px;
            font-weight: bold;
            color: {Colors.TEXT_PRIMARY};
            background: transparent;
            border: none;
        """)
        
        self.attr_table.setStyleSheet(f"""
            QTableWidget {{
                alternate-background-color: {Colors.BG_MEDIUM};
            }}
        """)
        
        self.fav_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.BG_CARD};
                border: 1px solid {Colors.NODE_OBJECT};
                border-radius: 8px;
                color: {Colors.NODE_OBJECT};
                font-weight: bold;
                padding: 8px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {Colors.NODE_OBJECT};
                color: white;
            }}
        """)

    def update_info(self, info: NodeInfo):
        """Update the properties display with new node info."""
        self._current_node = info

        # Node info table
        values = [
            info.node_id,
            info.browse_name,
            info.display_name,
            info.node_class.value,
            info.description,
            str(info.write_mask),
            str(info.user_write_mask),
        ]
        for i, val in enumerate(values):
            item = QTableWidgetItem(str(val))
            self.info_table.setItem(i, 1, item)

        # Attributes table
        attr_values = [
            str(info.executable) if info.node_class == NodeType.METHOD else "N/A",
            str(info.user_executable) if info.node_class == NodeType.METHOD else "N/A",
            str(info.event_notifier),
            str(info.write_mask),
            str(info.user_write_mask),
        ]
        for i, val in enumerate(attr_values):
            item = QTableWidgetItem(val)
            self.attr_table.setItem(i, 1, item)

    def _on_add_favorite(self):
        if self._current_node:
            self.add_to_favorites.emit(
                self._current_node.node_id,
                self._current_node.display_name,
                self._current_node.node_class,
            )


class DataAccessTab(QWidget):
    """Combined tab for reading (auto-refreshing) and writing values to variable nodes."""

    value_written = pyqtSignal(str, str)  # node_id, value string

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._opcua_client = None
        self._server_name = ""
        self._node_id = ""
        self._node_name = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)

        # ---- READ SECTION ----
        read_group = QFrame()
        read_layout = QVBoxLayout(read_group)
        read_layout.setContentsMargins(12, 12, 12, 12)
        read_layout.setSpacing(8)

        header_layout = QHBoxLayout()
        self.val_label = QLabel("Current Value")
        header_layout.addWidget(self.val_label)
        
        header_layout.addStretch()
        
        self.subscribe_cb = QCheckBox("Monitor (Subscribe)")
        self.subscribe_cb.stateChanged.connect(self._on_subscribe_toggled)
        header_layout.addWidget(self.subscribe_cb)
        
        self.refresh_btn = QPushButton("⟳ Refresh")
        self.refresh_btn.setProperty("class", "primary")
        self.refresh_btn.clicked.connect(self._on_manual_refresh)
        header_layout.addWidget(self.refresh_btn)

        read_layout.addLayout(header_layout)

        self.value_display = QTextEdit()
        self.value_display.setReadOnly(True)
        self.value_display.setMaximumHeight(80)
        read_layout.addWidget(self.value_display)

        footer_layout = QHBoxLayout()
        self.type_display = QLabel("Type: —")
        footer_layout.addWidget(self.type_display)
        footer_layout.addStretch()
        self.timestamp_label = QLabel("Last updated: —")
        footer_layout.addWidget(self.timestamp_label)
        read_layout.addLayout(footer_layout)

        layout.addWidget(read_group)

        # ---- WRITE SECTION ----
        write_group = QFrame()
        write_layout = QVBoxLayout(write_group)
        write_layout.setContentsMargins(12, 12, 12, 12)
        write_layout.setSpacing(8)

        self.write_title = QLabel("Write New Value")
        write_layout.addWidget(self.write_title)

        form_layout = QHBoxLayout()
        
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "String", "Boolean", "Int16", "Int32", "Int64",
            "UInt16", "UInt32", "UInt64", "Float", "Double",
            "Byte", "ByteString", "DateTime",
        ])
        self.type_combo.setFixedWidth(100)
        form_layout.addWidget(self.type_combo)

        self.value_input = QLineEdit()
        self.value_input.setPlaceholderText("Enter value to write...")
        form_layout.addWidget(self.value_input)

        self.write_btn = QPushButton("✏️ Write")
        self.write_btn.setProperty("class", "primary")
        self.write_btn.clicked.connect(self._on_write)
        form_layout.addWidget(self.write_btn)

        write_layout.addLayout(form_layout)

        self.status_label = QLabel("")
        write_layout.addWidget(self.status_label)

        layout.addWidget(write_group)

        # Style reference for the frames
        self.read_group = read_group
        self.write_group = write_group

        layout.addStretch()

        self.update_theme()
        theme_manager.theme_changed.connect(self.update_theme)

    def update_theme(self):
        card_style = f"""
            QFrame {{
                background-color: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
            }}
        """
        self.read_group.setStyleSheet(card_style)
        self.write_group.setStyleSheet(card_style)

        self.val_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {Colors.TEXT_PRIMARY}; border: none;")
        self.write_title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {Colors.TEXT_PRIMARY}; border: none;")

        self.value_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Colors.BG_INPUT};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
                padding: 6px;
                font-family: 'Menlo', 'Courier New', 'Courier';
                font-size: 13px;
                color: {Colors.ACCENT};
            }}
        """)

        self.type_display.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px; font-weight: bold; border: none;")
        self.subscribe_cb.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; border: none;")
        self.timestamp_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px; border: none;")

        if not self.status_label.text():
            self.status_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; border: none;")
        elif "❌" in self.status_label.text():
            self.status_label.setStyleSheet(f"color: {Colors.ERROR}; border: none;")
        else:
            self.status_label.setStyleSheet(f"color: {Colors.SUCCESS}; border: none;")

    def set_client(self, client, server_name: str = ""):
        self._opcua_client = client
        self._server_name = server_name

    def set_node(self, node_id: str, info: NodeInfo):
        self._node_id = node_id
        self._node_name = info.display_name
        
        # Read part
        if info.value is not None:
            self.value_display.setText(str(info.value))
            self.value_input.setText(str(info.value))
        else:
            self.value_display.setText("—")
        self.type_display.setText(f"Type: {info.data_type if info.data_type else '—'}")
        self._update_timestamp()

        # Write part
        if info.data_type:
            idx = self.type_combo.findText(info.data_type)
            if idx >= 0:
                self.type_combo.setCurrentIndex(idx)

    def _on_manual_refresh(self):
        if self._node_id and self._opcua_client:
            asyncio.ensure_future(self._refresh_value())

    def _on_subscribe_toggled(self, state: int):
        if not self._node_id or not self._opcua_client:
            return
        import asyncio
        if state == 2:  # Checked
            asyncio.ensure_future(self._opcua_client.subscribe_node(self._node_id, self._node_name))
        else:
            asyncio.ensure_future(self._opcua_client.unsubscribe_node(self._node_id))

    async def _refresh_value(self):
        if not self._node_id or not self._opcua_client:
            return
        value = await self._opcua_client.read_value(self._node_id, self._server_name)
        if value is not None:
            self.value_display.setText(str(value))
        self._update_timestamp()

    def stop_auto_refresh(self):
        pass  # Kept for compatibility if called elsewhere

    def _update_timestamp(self):
        from datetime import datetime
        now = datetime.now().strftime("%H:%M:%S")
        self.timestamp_label.setText(f"Last updated: {now}")

    def _on_write(self):
        if self._node_id and self._opcua_client:
            asyncio.ensure_future(self._write_value())

    async def _write_value(self):
        if not self._node_id or not self._opcua_client:
            return

        raw_value = self.value_input.text()
        data_type = self.type_combo.currentText()

        try:
            value = self._convert_value(raw_value, data_type)
        except Exception as e:
            self.status_label.setText(f"❌ Invalid value: {e}")
            self.status_label.setStyleSheet(f"color: {Colors.ERROR}; border: none;")
            return

        success = await self._opcua_client.write_value(
            self._node_id, value, data_type, self._server_name
        )

        if success:
            self.status_label.setText(f"✅ Value written successfully")
            self.status_label.setStyleSheet(f"color: {Colors.SUCCESS}; border: none;")
            self.value_written.emit(self._node_id, raw_value)
            # update read display as well
            self.value_display.setText(raw_value)
            self._update_timestamp()
        else:
            self.status_label.setText(f"❌ Write failed")
            self.status_label.setStyleSheet(f"color: {Colors.ERROR}; border: none;")

    def _convert_value(self, raw: str, data_type: str) -> Any:
        converters = {
            "String": str,
            "Boolean": lambda v: v.lower() in ("true", "1", "yes"),
            "Int16": int,
            "Int32": int,
            "Int64": int,
            "UInt16": int,
            "UInt32": int,
            "UInt64": int,
            "Float": float,
            "Double": float,
            "Byte": int,
            "ByteString": lambda v: bytes(v, "utf-8"),
        }
        converter = converters.get(data_type, str)
        return converter(raw)


class CallMethodTab(QWidget):
    """Tab for calling OPC UA methods."""

    method_called = pyqtSignal(str, str)  # method_node_id, result
    add_to_favorites_requested = pyqtSignal(str, str, NodeType, list)  # node_id, name, type, args

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._method_node_id: Optional[str] = None
        self._parent_node_id: Optional[str] = None
        self._method_display_name: str = ""
        self._opcua_client = None
        self._server_name = ""
        self._input_args: list[MethodArgument] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Method selector
        method_layout = QHBoxLayout()
        self.method_label = QLabel("Method:")
        method_layout.addWidget(self.method_label)

        self.method_id_label = QLabel("—")
        self.method_id_label.setWordWrap(True)
        method_layout.addWidget(self.method_id_label, 1)
        layout.addLayout(method_layout)

        # Input Parameters
        self.input_label = QLabel("Input Parameters")
        layout.addWidget(self.input_label)

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
        self.params_table.setMinimumHeight(150)
        self.params_table.setMaximumHeight(250)
        layout.addWidget(self.params_table)

        btn_layout = QHBoxLayout()
        self.call_btn = QPushButton("▶  Call")
        self.call_btn.setProperty("class", "primary")
        self.call_btn.setMinimumWidth(140)
        self.call_btn.setMinimumHeight(34)
        self.call_btn.clicked.connect(self._on_call)
        btn_layout.addWidget(self.call_btn)

        self.fav_btn = QPushButton("⭐ Favorite")
        self.fav_btn.setMinimumHeight(34)
        self.fav_btn.clicked.connect(self._on_favorite)
        btn_layout.addWidget(self.fav_btn)

        btn_layout.addStretch()

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self._on_clear)
        btn_layout.addWidget(self.clear_btn)

        layout.addLayout(btn_layout)

        # Output
        self.output_label = QLabel("Output")
        layout.addWidget(self.output_label)

        self.output_table = QTableWidget(0, 4)
        self.output_table.setHorizontalHeaderLabels(["#", "Name", "Type", "Value"])
        self.output_table.horizontalHeader().setStretchLastSection(True)
        self.output_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed
        )
        self.output_table.setColumnWidth(0, 30)
        self.output_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.output_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.output_table.verticalHeader().setVisible(False)
        self.output_table.verticalHeader().setDefaultSectionSize(36)
        self.output_table.setMinimumHeight(120)
        self.output_table.setMaximumHeight(200)
        
        layout.addWidget(self.output_table)

        layout.addStretch()

        self.update_theme()
        theme_manager.theme_changed.connect(self.update_theme)

    def update_theme(self):
        self.method_label.setStyleSheet(f"font-weight: bold; color: {Colors.TEXT_PRIMARY}; background: transparent;")
        self.method_id_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent;")
        
        self.input_label.setStyleSheet(f"""
            font-size: 12px;
            font-weight: bold;
            color: {Colors.TEXT_PRIMARY};
            background: transparent;
        """)
        
        self.fav_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {Colors.NODE_METHOD};
                border-radius: 6px;
                color: {Colors.NODE_METHOD};
                font-weight: bold;
                padding: 6px 16px;
            }}
            QPushButton:hover {{
                background-color: {Colors.NODE_METHOD};
                color: white;
            }}
        """)
        
        self.output_label.setStyleSheet(f"""
            font-size: 12px;
            font-weight: bold;
            color: {Colors.TEXT_PRIMARY};
            background: transparent;
        """)
        
        # We need to re-render combo boxes and line edits in the params table if they exist.
        # But wait, we can just call `_populate_params` with existing args.
        if self._input_args:
            # Re-populating will reset user's typed values, so let's save them first.
            saved_vals = []
            for i in range(self.params_table.rowCount()):
                val_widget = self.params_table.cellWidget(i, 3)
                if isinstance(val_widget, QLineEdit):
                    saved_vals.append(val_widget.text())
                elif isinstance(val_widget, QComboBox):
                    saved_vals.append(val_widget.currentText())
                else:
                    saved_vals.append("")

            if hasattr(self, '_method_node_id'):
                self.set_method(self._method_node_id, self._method_display_name, self._parent_node_id, self._input_args, getattr(self, '_output_args', []))            # Restore values
            for i in range(min(len(saved_vals), self.params_table.rowCount())):
                val_widget = self.params_table.cellWidget(i, 3)
                if isinstance(val_widget, QLineEdit):
                    val_widget.setText(saved_vals[i])
                elif isinstance(val_widget, QComboBox):
                    idx = val_widget.findText(saved_vals[i])
                    if idx >= 0:
                        val_widget.setCurrentIndex(idx)

    def set_client(self, client, server_name: str = ""):
        self._opcua_client = client
        self._server_name = server_name

    def set_method(self, method_node_id: str, method_display_name: str, parent_node_id: str, input_args: list[MethodArgument], output_args: list[MethodArgument] = None):
        """Set the method to call and populate parameters."""
        self._method_node_id = method_node_id
        self._method_display_name = method_display_name
        self._parent_node_id = parent_node_id
        self._input_args = input_args
        if output_args is None:
            output_args = []
        self._output_args = output_args

        self.method_id_label.setText(method_node_id)

        # Set up input table
        self.params_table.setRowCount(len(input_args))
        for i, arg in enumerate(input_args):
            self.params_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.params_table.setItem(i, 1, QTableWidgetItem(arg.name))
            type_item = QTableWidgetItem(arg.data_type)
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.params_table.setItem(i, 2, type_item)
            
            if arg.data_type == "Boolean":
                from PyQt6.QtWidgets import QComboBox
                combo = QComboBox()
                combo.addItems(["False", "True"])
                combo.setStyleSheet(f"""
                    QComboBox {{
                        background-color: {Colors.BG_INPUT};
                        color: {Colors.TEXT_PRIMARY};
                        border: 1px solid {Colors.BORDER};
                        border-radius: 4px;
                        padding: 2px 8px;
                    }}
                    QComboBox::drop-down {{
                        border-left: 1px solid {Colors.BORDER};
                        width: 20px;
                    }}
                """)
                if arg.value is not None:
                    combo.setCurrentText(str(arg.value).capitalize())
                self.params_table.setCellWidget(i, 3, combo)
            else:
                self.params_table.setItem(i, 3, QTableWidgetItem(str(arg.value or "")))

        # Make Input # and Name non-editable
        for i in range(len(input_args)):
            for col in (0, 1, 2):
                item = self.params_table.item(i, col)
                if item:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

        # Set up output table
        self.output_table.setRowCount(len(output_args))
        for i, arg in enumerate(output_args):
            self.output_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.output_table.setItem(i, 1, QTableWidgetItem(arg.name))
            type_item = QTableWidgetItem(arg.data_type)
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.output_table.setItem(i, 2, type_item)
            self.output_table.setItem(i, 3, QTableWidgetItem(""))
            
            # Make Output #, Name, and Type non-editable
            for col in (0, 1, 2):
                item = self.output_table.item(i, col)
                if item:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            # Output value is also read-only
            val_item = self.output_table.item(i, 3)
            if val_item:
                val_item.setFlags(val_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

    def populate_saved_args(self, args: list):
        """Restore saved arguments into the table."""
        for i, val in enumerate(args):
            if i < self.params_table.rowCount():
                combo = self.params_table.cellWidget(i, 3)
                if combo:
                    combo.setCurrentText(str(val))
                else:
                    item = self.params_table.item(i, 3)
                    if item:
                        item.setText(str(val))

    def _on_favorite(self):
        if self._method_node_id:
            name = self._method_display_name or self._method_node_id
            
            # Gather current input args
            saved_args = []
            for i in range(self.params_table.rowCount()):
                combo = self.params_table.cellWidget(i, 3)
                if combo:
                    saved_args.append(combo.currentText())
                else:
                    val_item = self.params_table.item(i, 3)
                    if val_item:
                        saved_args.append(val_item.text())
            
            self.add_to_favorites_requested.emit(
                self._method_node_id, name, NodeType.METHOD, saved_args
            )

    def _on_call(self):
        if self._method_node_id and self._opcua_client:
            asyncio.ensure_future(self._call_method())

    async def _call_method(self):
        if not self._method_node_id or not self._opcua_client:
            return

        # Gather args from table
        args = []
        for i in range(self.params_table.rowCount()):
            type_item = self.params_table.item(i, 2)
            if not type_item:
                continue
                
            data_type = type_item.text()
            combo = self.params_table.cellWidget(i, 3)
            
            if combo:
                raw_val = combo.currentText()
            else:
                val_item = self.params_table.item(i, 3)
                if not val_item:
                    continue
                raw_val = val_item.text()
                
            try:
                args.append(self._convert_arg(raw_val, data_type))
            except Exception:
                args.append(raw_val)

        result = await self._opcua_client.call_method(
            self._parent_node_id, self._method_node_id,
            args, self._server_name
        )

        if result is not None:
            # result could be a single value or a list of values
            if not isinstance(result, (list, tuple)):
                result = [result]
                
            for i, val in enumerate(result):
                if i < self.output_table.rowCount():
                    item = self.output_table.item(i, 3)
                    if not item:
                        item = QTableWidgetItem()
                        self.output_table.setItem(i, 3, item)
                    item.setText(str(val))
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.method_called.emit(self._method_node_id, str(result))
        else:
            for i in range(self.output_table.rowCount()):
                item = self.output_table.item(i, 3)
                if item:
                    item.setText("")
            self.method_called.emit(self._method_node_id, "()")

    def _on_clear(self):
        for i in range(self.params_table.rowCount()):
            item = self.params_table.item(i, 3)
            if item:
                item.setText("")
        for i in range(self.output_table.rowCount()):
            item = self.output_table.item(i, 3)
            if item:
                item.setText("")

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


class NodeInfoWidget(QWidget):
    """Tabbed widget showing Properties / Value / Write / Call Method tabs."""

    add_to_favorites = pyqtSignal(str, str, NodeType, list)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()

        # Create tabs
        self.properties_tab = PropertiesTab()
        self.data_access_tab = DataAccessTab()
        self.call_method_tab = CallMethodTab()

        self.tabs.addTab(self.properties_tab, "Properties")
        self.tabs.addTab(self.data_access_tab, "Data Access")
        self.tabs.addTab(self.call_method_tab, "Call Method")

        # Forward favorites signals
        self.properties_tab.add_to_favorites.connect(
            lambda nid, name, ntype: self.add_to_favorites.emit(nid, name, ntype, [])
        )
        self.call_method_tab.add_to_favorites_requested.connect(self.add_to_favorites.emit)

        layout.addWidget(self.tabs)

    def set_client(self, client, server_name: str = ""):
        self.data_access_tab.set_client(client, server_name)
        self.call_method_tab.set_client(client, server_name)

    def update_node(self, info: NodeInfo):
        """Update all tabs with node information."""
        self.properties_tab.update_info(info)
        self.data_access_tab.set_node(info.node_id, info)

        # Switch to relevant tab based on node type
        if info.node_class == NodeType.METHOD:
            self.tabs.setCurrentWidget(self.call_method_tab)
        elif info.node_class == NodeType.VARIABLE:
            self.tabs.setCurrentIndex(0)  # Properties tab

    def set_method(self, method_node_id: str, method_display_name: str, parent_node_id: str, input_args: list[MethodArgument], output_args: list[MethodArgument] = None):
        """Set method info for the Call Method tab."""
        self.call_method_tab.set_method(method_node_id, method_display_name, parent_node_id, input_args, output_args)
        self.tabs.setCurrentWidget(self.call_method_tab)
