"""Favorites panel widget — right sidebar showing bookmarked nodes."""

import json
import os
from typing import Optional

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy, QMenu,
)

from app.models import FavoriteItem, NodeType
from app.theme import Colors

FAVORITES_FILE = os.path.join(os.path.expanduser("~"), ".opcua_client_favorites.json")


class FavoriteCard(QFrame):
    """A single favorite item card."""

    clicked = pyqtSignal(FavoriteItem)
    remove_requested = pyqtSignal(FavoriteItem)

    def __init__(self, item: FavoriteItem, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.fav_item = item
        self._setup_ui()
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _setup_ui(self):
        self.setStyleSheet(f"""
            FavoriteCard {{
                background-color: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER};
                border-radius: 10px;
            }}
            FavoriteCard:hover {{
                border-color: {Colors.BORDER_LIGHT};
                background-color: {Colors.BG_HOVER};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 8, 10)
        layout.setSpacing(10)

        # Info section
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        # Name + badge
        name_row = QHBoxLayout()
        name_label = QLabel(self.fav_item.display_name)
        name_label.setStyleSheet(f"""
            font-weight: bold;
            font-size: 13px;
            color: {Colors.TEXT_PRIMARY};
            background: transparent;
        """)
        name_row.addWidget(name_label)

        # Type badge
        badge = QLabel(self.fav_item.node_type.value)
        if self.fav_item.node_type == NodeType.VARIABLE:
            badge.setStyleSheet(f"""
                background-color: {Colors.BADGE_VARIABLE};
                color: {Colors.BADGE_VARIABLE_TEXT};
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 9px;
                font-weight: bold;
            """)
        elif self.fav_item.node_type == NodeType.METHOD:
            badge.setStyleSheet(f"""
                background-color: {Colors.BADGE_METHOD};
                color: {Colors.BADGE_METHOD_TEXT};
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 9px;
                font-weight: bold;
            """)
        else:
            badge.setStyleSheet(f"""
                background-color: {Colors.BG_SURFACE};
                color: {Colors.TEXT_SECONDARY};
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 9px;
                font-weight: bold;
            """)
        name_row.addWidget(badge)
        name_row.addStretch()
        info_layout.addLayout(name_row)

        # Server Name
        if self.fav_item.server_name:
            server_label = QLabel(f"🖧 {self.fav_item.server_name}")
            server_label.setStyleSheet(f"""
                font-size: 11px;
                color: {Colors.TEXT_SECONDARY};
                background: transparent;
            """)
            info_layout.addWidget(server_label)

        # Node ID
        node_id_label = QLabel(self.fav_item.node_id)
        node_id_label.setStyleSheet(f"""
            font-size: 10px;
            color: {Colors.TEXT_MUTED};
            background: transparent;
        """)
        node_id_label.setWordWrap(True)
        info_layout.addWidget(node_id_label)

        layout.addLayout(info_layout, 1)

        # Remove button
        remove_btn = QPushButton("✕")
        remove_btn.setFixedSize(22, 22)
        remove_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {Colors.TEXT_MUTED};
                font-size: 14px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                color: {Colors.ERROR};
                background-color: {Colors.ERROR_BG};
            }}
        """)
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.clicked.connect(lambda: self.remove_requested.emit(self.fav_item))
        layout.addWidget(remove_btn, 0, Qt.AlignmentFlag.AlignTop)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.fav_item)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        
        # Load/Call action
        action_text = "▶ Call Method" if self.fav_item.node_type == NodeType.METHOD else "👁 Load Node"
        load_action = menu.addAction(action_text)
        
        menu.addSeparator()
        
        # Delete action
        delete_action = menu.addAction("🗑 Delete")
        
        # Style the menu
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
                color: {Colors.TEXT_PRIMARY};
            }}
            QMenu::item {{
                padding: 6px 24px 6px 12px;
            }}
            QMenu::item:selected {{
                background-color: {Colors.BG_HOVER};
            }}
        """)
        
        action = menu.exec(event.globalPos())
        if action == load_action:
            self.clicked.emit(self.fav_item)
        elif action == delete_action:
            self.remove_requested.emit(self.fav_item)


class FavoritesPanel(QWidget):
    """Right sidebar showing favorited OPC UA nodes."""

    favorite_clicked = pyqtSignal(FavoriteItem)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._cards: list[FavoriteCard] = []
        self._setup_ui()
        self._load_favorites()

    def _setup_ui(self):
        self.setMinimumWidth(220)
        self.setMaximumWidth(300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Panel container
        panel = QFrame()
        panel.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_DARK};
                border: 1px solid {Colors.BORDER};
                border-radius: 12px;
            }}
        """)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 14, 12, 14)
        panel_layout.setSpacing(10)

        # Header
        header_layout = QHBoxLayout()
        star_icon = QLabel("⭐")
        star_icon.setStyleSheet("font-size: 16px; background: transparent;")
        header_layout.addWidget(star_icon)

        title = QLabel("Favorites")
        title.setStyleSheet(f"""
            font-size: 15px;
            font-weight: bold;
            color: {Colors.TEXT_PRIMARY};
            background: transparent;
        """)
        header_layout.addWidget(title)
        header_layout.addStretch()
        panel_layout.addLayout(header_layout)

        # Scrollable list
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

        layout.addWidget(panel)

    def add_favorite(self, node_id: str, display_name: str, node_type: NodeType,
                     server_url: str = "", server_name: str = "", args: list = None):
        """Add a node to favorites."""
        # Check if already exists
        for card in self._cards:
            if card.fav_item.node_id == node_id:
                return

        item = FavoriteItem(
            display_name=display_name,
            node_id=node_id,
            node_type=node_type,
            server_url=server_url,
            server_name=server_name,
            input_args=args or [],
        )
        self._add_card(item)
        self._save_favorites()

    def _add_card(self, item: FavoriteItem):
        card = FavoriteCard(item)
        card.clicked.connect(self.favorite_clicked.emit)
        card.remove_requested.connect(self._remove_favorite)
        self._cards.append(card)
        self.list_layout.insertWidget(self.list_layout.count() - 1, card)

    def _remove_favorite(self, item: FavoriteItem):
        for card in self._cards:
            if card.fav_item.node_id == item.node_id:
                self._cards.remove(card)
                card.deleteLater()
                break
        self._save_favorites()

    def _save_favorites(self):
        data = [card.fav_item.to_dict() for card in self._cards]
        try:
            with open(FAVORITES_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _load_favorites(self):
        try:
            if os.path.exists(FAVORITES_FILE):
                with open(FAVORITES_FILE, "r") as f:
                    data = json.load(f)
                for item_data in data:
                    item = FavoriteItem.from_dict(item_data)
                    self._add_card(item)
        except Exception:
            pass
