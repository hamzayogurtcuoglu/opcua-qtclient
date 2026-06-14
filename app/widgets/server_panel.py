"""Server panel widget — left sidebar showing available OPC UA servers."""

import asyncio
from typing import Optional

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QIcon, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QFrame, QMenu, QSizePolicy,
)

from app.models import ServerInfo, ConnectionStatus
from app.theme import Colors, theme_manager


class ServerCard(QFrame):
    """A single server entry card."""

    clicked = pyqtSignal(ServerInfo)
    connect_requested = pyqtSignal(ServerInfo)
    disconnect_requested = pyqtSignal(ServerInfo)
    remove_requested = pyqtSignal(ServerInfo)
    edit_requested = pyqtSignal(ServerInfo)

    def __init__(self, server_info: ServerInfo, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.server_info = server_info
        self._setup_ui()
        self.update_status(server_info.status)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _setup_ui(self):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFixedHeight(68)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        # Text section
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        self.name_label = QLabel(self.server_info.name)
        self.url_label = QLabel(self.server_info.url)

        text_layout.addWidget(self.name_label)
        text_layout.addWidget(self.url_label)
        layout.addLayout(text_layout, 1)

        # Status badge
        self.status_badge = QLabel()
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.setFixedHeight(22)
        self.status_badge.setStyleSheet(f"""
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 10px;
            font-weight: bold;
        """)
        layout.addWidget(self.status_badge)

        self.update_theme()
        theme_manager.theme_changed.connect(self.update_theme)

    def update_theme(self):
        self.setStyleSheet(f"""
            ServerCard {{
                background-color: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER};
                border-radius: 10px;
                padding: 0px;
            }}
            ServerCard:hover {{
                border-color: {Colors.BORDER_LIGHT};
                background-color: {Colors.BG_HOVER};
            }}
        """)

        self.name_label.setStyleSheet(f"""
            font-weight: bold;
            font-size: 13px;
            color: {Colors.TEXT_PRIMARY};
            background: transparent;
        """)

        self.url_label.setStyleSheet(f"""
            font-size: 11px;
            color: {Colors.TEXT_MUTED};
            background: transparent;
        """)

        # Re-apply status styling with new theme
        self.update_status(self.server_info.status)

    def update_status(self, status: ConnectionStatus):
        self.server_info.status = status
        if status == ConnectionStatus.CONNECTED:
            self.status_badge.setText("Connected")
            self.status_badge.setStyleSheet(f"""
                background-color: {Colors.SUCCESS_BG};
                color: {Colors.SUCCESS};
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: bold;
            """)
        elif status == ConnectionStatus.CONNECTING:
            self.status_badge.setText("Connecting...")
            self.status_badge.setStyleSheet(f"""
                background-color: {Colors.WARNING_BG};
                color: {Colors.WARNING};
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: bold;
            """)
        elif status == ConnectionStatus.ERROR:
            self.status_badge.setText("Error")
            self.status_badge.setStyleSheet(f"""
                background-color: {Colors.ERROR_BG};
                color: {Colors.ERROR};
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: bold;
            """)
        else:
            self.status_badge.setText("Not Connected")
            self.status_badge.setStyleSheet(f"""
                background-color: {Colors.BG_SURFACE};
                color: {Colors.TEXT_MUTED};
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: bold;
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.server_info)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.server_info.status == ConnectionStatus.CONNECTED:
                self.clicked.emit(self.server_info)
            else:
                self.connect_requested.emit(self.server_info)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        if self.server_info.status == ConnectionStatus.CONNECTED:
            disconnect_action = menu.addAction("⚡ Disconnect")
            disconnect_action.triggered.connect(
                lambda: self.disconnect_requested.emit(self.server_info)
            )
        else:
            connect_action = menu.addAction("🔌 Connect")
            connect_action.triggered.connect(
                lambda: self.connect_requested.emit(self.server_info)
            )

        menu.addSeparator()
        edit_action = menu.addAction("✏️ Edit")
        edit_action.triggered.connect(
            lambda: self.edit_requested.emit(self.server_info)
        )
        remove_action = menu.addAction("🗑️ Remove")
        remove_action.triggered.connect(
            lambda: self.remove_requested.emit(self.server_info)
        )
        menu.exec(event.globalPos())


class ServerPanel(QWidget):
    """Left sidebar panel showing all OPC UA servers."""

    server_connect_requested = pyqtSignal(ServerInfo)
    server_disconnect_requested = pyqtSignal(ServerInfo)
    server_clicked = pyqtSignal(ServerInfo)
    add_server_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._cards: list[ServerCard] = []
        self._setup_ui()

    def _setup_ui(self):
        self.setMinimumWidth(240)
        self.setMaximumWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Panel container
        self.panel = QFrame()
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(12, 14, 12, 14)
        panel_layout.setSpacing(10)

        # Header
        header_layout = QHBoxLayout()
        self.title_label = QLabel("Servers")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        self.refresh_btn = QPushButton("⟳")
        self.refresh_btn.setFixedSize(28, 28)
        header_layout.addWidget(self.refresh_btn)
        panel_layout.addLayout(header_layout)

        # Search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search servers...")
        self.search_input.textChanged.connect(self._filter_servers)
        panel_layout.addWidget(self.search_input)

        # Server list (scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self.list_widget = QWidget()
        self.list_widget.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(6)
        self.list_layout.addStretch()

        scroll.setWidget(self.list_widget)
        panel_layout.addWidget(scroll, 1)

        # Add server button
        self.add_btn = QPushButton("+ Add Server Manually")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.clicked.connect(self.add_server_requested.emit)
        panel_layout.addWidget(self.add_btn)

        # Legend
        legend_layout = QHBoxLayout()
        legend_layout.setSpacing(12)
        self.legend_text_labels = []
        for icon, label in [
            ("🟡", "Object"), ("🔵", "Variable"), ("🟣", "Method"), ("👁", "View")
        ]:
            item_layout = QHBoxLayout()
            item_layout.setSpacing(4)
            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet("font-size: 10px; background: transparent;")
            text_lbl = QLabel(label)
            self.legend_text_labels.append(text_lbl)
            item_layout.addWidget(icon_lbl)
            item_layout.addWidget(text_lbl)
            legend_layout.addLayout(item_layout)
        legend_layout.addStretch()
        panel_layout.addLayout(legend_layout)

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

        self.title_label.setStyleSheet(f"""
            font-size: 15px;
            font-weight: bold;
            color: {Colors.TEXT_PRIMARY};
            background: transparent;
            border: none;
        """)

        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {Colors.TEXT_SECONDARY};
                font-size: 16px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {Colors.BG_HOVER};
                color: {Colors.TEXT_PRIMARY};
            }}
        """)

        self.add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px dashed {Colors.BORDER_LIGHT};
                border-radius: 10px;
                color: {Colors.TEXT_SECONDARY};
                padding: 10px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                border-color: {Colors.ACCENT};
                color: {Colors.ACCENT};
                background-color: {Colors.BG_HOVER};
            }}
        """)

        # Legend items
        for lbl in self.legend_text_labels:
            lbl.setStyleSheet(f"font-size: 10px; color: {Colors.TEXT_MUTED}; background: transparent;")

    def add_server(self, server_info: ServerInfo):
        """Add a new server card to the panel."""
        card = ServerCard(server_info)
        card.clicked.connect(self.server_clicked.emit)
        card.connect_requested.connect(self.server_connect_requested.emit)
        card.disconnect_requested.connect(self.server_disconnect_requested.emit)
        card.remove_requested.connect(self._remove_server)
        self._cards.append(card)
        # Insert before the stretch
        self.list_layout.insertWidget(self.list_layout.count() - 1, card)

    def _remove_server(self, server_info: ServerInfo):
        for card in self._cards:
            if card.server_info.url == server_info.url:
                self._cards.remove(card)
                card.deleteLater()
                break

    def update_server_status(self, url: str, status: ConnectionStatus):
        """Update the status badge of a server card."""
        for card in self._cards:
            if card.server_info.url == url:
                card.update_status(status)
                break

    def get_server_by_url(self, url: str) -> Optional[ServerInfo]:
        for card in self._cards:
            if card.server_info.url == url:
                return card.server_info
        return None

    def get_all_servers(self) -> list[ServerInfo]:
        return [card.server_info for card in self._cards]

    def _filter_servers(self, text: str):
        """Filter server cards based on search text."""
        text = text.lower()
        for card in self._cards:
            visible = (
                text in card.server_info.name.lower()
                or text in card.server_info.url.lower()
            )
            card.setVisible(visible)
