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
from app.theme import Colors, menu_stylesheet, theme_manager

FAVORITES_FILE = os.path.join(os.path.expanduser("~"), ".opcua_client_favorites.json")


class FavoriteCard(QFrame):
    """A single favorite item card."""

    clicked = pyqtSignal(FavoriteItem)
    execute_requested = pyqtSignal(FavoriteItem)
    remove_requested = pyqtSignal(FavoriteItem)
    rename_requested = pyqtSignal(FavoriteItem)
    edit_requested = pyqtSignal(FavoriteItem)

    def __init__(self, item: FavoriteItem, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.fav_item = item
        self._setup_ui()
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 8, 10)
        layout.setSpacing(10)

        # Info section
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        # Name + badge
        name_row = QHBoxLayout()
        self.name_label = QLabel(self.fav_item.display_name)
        name_row.addWidget(self.name_label)

        # Type badge
        badge_text = self.fav_item.node_type.value
        self.badge = QLabel(badge_text)
        name_row.addWidget(self.badge)
        name_row.addStretch()
        info_layout.addLayout(name_row)

        # Server Name
        if self.fav_item.server_name:
            self.server_label = QLabel(f"🖧 {self.fav_item.server_name}")
            info_layout.addWidget(self.server_label)

        # Node ID
        self.node_id_label = QLabel(self._subtitle_text())
        self.node_id_label.setWordWrap(True)
        info_layout.addWidget(self.node_id_label)

        layout.addLayout(info_layout, 1)

        # Remove button
        self.remove_btn = QPushButton("✕")
        self.remove_btn.setFixedSize(22, 22)
        self.remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_btn.clicked.connect(lambda: self.remove_requested.emit(self.fav_item))
        layout.addWidget(self.remove_btn, 0, Qt.AlignmentFlag.AlignTop)

        self.update_theme()
        theme_manager.theme_changed.connect(self.update_theme)

    def _subtitle_text(self) -> str:
        """Secondary line under the name, tailored per favorite type."""
        if self.fav_item.node_type == NodeType.FLOW:
            n = len(self.fav_item.flow_steps or [])
            return f"\ud83e\udde9 {n} step{'s' if n != 1 else ''}"
        if self.fav_item.node_type == NodeType.WRITE:
            return f"= {self.fav_item.write_value}  ({self.fav_item.write_data_type})"
        return self.fav_item.node_id

    def update_theme(self):
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

        self.name_label.setStyleSheet(f"""
            font-weight: bold;
            font-size: 13px;
            color: {Colors.TEXT_PRIMARY};
            background: transparent;
        """)

        if self.fav_item.node_type == NodeType.VARIABLE:
            self.badge.setStyleSheet(f"""
                background-color: {Colors.BADGE_VARIABLE};
                color: {Colors.BADGE_VARIABLE_TEXT};
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 9px;
                font-weight: bold;
            """)
        elif self.fav_item.node_type == NodeType.METHOD:
            self.badge.setStyleSheet(f"""
                background-color: {Colors.BADGE_METHOD};
                color: {Colors.BADGE_METHOD_TEXT};
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 9px;
                font-weight: bold;
            """)
        elif self.fav_item.node_type == NodeType.SCRIPT:
            self.badge.setStyleSheet(f"""
                background-color: {Colors.SUCCESS_BG};
                color: {Colors.SUCCESS};
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 9px;
                font-weight: bold;
            """)
        elif self.fav_item.node_type == NodeType.WRITE:
            self.badge.setStyleSheet(f"""
                background-color: {Colors.WARNING_BG};
                color: {Colors.WARNING};
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 9px;
                font-weight: bold;
            """)
        elif self.fav_item.node_type == NodeType.FLOW:
            self.badge.setStyleSheet(f"""
                background-color: {Colors.ACCENT};
                color: white;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 9px;
                font-weight: bold;
            """)
        else:
            self.badge.setStyleSheet(f"""
                background-color: {Colors.BG_SURFACE};
                color: {Colors.TEXT_SECONDARY};
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 9px;
                font-weight: bold;
            """)

        if hasattr(self, 'server_label'):
            self.server_label.setStyleSheet(f"""
                font-size: 11px;
                color: {Colors.TEXT_SECONDARY};
                background: transparent;
            """)

        self.node_id_label.setStyleSheet(f"""
            font-size: 10px;
            color: {Colors.TEXT_MUTED};
            background: transparent;
        """)

        self.remove_btn.setStyleSheet(f"""
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

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Single click only loads/navigates — it never executes.
            self.clicked.emit(self.fav_item)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Double click runs the method / script.
            self.execute_requested.emit(self.fav_item)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)

        ntype = self.fav_item.node_type
        runnable = ntype in (NodeType.METHOD, NodeType.SCRIPT, NodeType.WRITE, NodeType.FLOW)

        # Run/Call action (only for executable favorites)
        run_action = None
        if runnable:
            run_text = {
                NodeType.SCRIPT: "▶ Run Script",
                NodeType.METHOD: "▶ Call Method",
                NodeType.WRITE: "▶ Set Value",
                NodeType.FLOW: "▶ Run Flow",
            }.get(ntype, "▶ Run")
            run_action = menu.addAction(run_text)

        # Flow editing
        edit_action = None
        if ntype == NodeType.FLOW:
            edit_action = menu.addAction("🧩 Edit Flow")

        # Load/open action — never executes
        load_action = menu.addAction("👁 Open / Load")

        menu.addSeparator()

        # Rename action
        rename_action = menu.addAction("✏️ Rename")

        menu.addSeparator()

        # Delete action
        delete_action = menu.addAction("🗑 Delete")

        menu.setStyleSheet(menu_stylesheet())

        action = menu.exec(event.globalPos())
        if run_action is not None and action == run_action:
            self.execute_requested.emit(self.fav_item)
        elif edit_action is not None and action == edit_action:
            self.edit_requested.emit(self.fav_item)
        elif action == load_action:
            self.clicked.emit(self.fav_item)
        elif action == rename_action:
            self.rename_requested.emit(self.fav_item)
        elif action == delete_action:
            self.remove_requested.emit(self.fav_item)


class FavoritesPanel(QWidget):
    """Right sidebar showing favorited OPC UA nodes."""

    favorite_clicked = pyqtSignal(FavoriteItem)
    favorite_execute = pyqtSignal(FavoriteItem)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._cards: list[FavoriteCard] = []
        self._setup_ui()
        self._load_favorites()

    def _setup_ui(self):
        self.setMinimumWidth(220)

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
        star_icon = QLabel("★")
        star_icon.setStyleSheet("font-size: 16px; background: transparent;")
        header_layout.addWidget(star_icon)

        self.title_label = QLabel("Favorites")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        self.new_flow_btn = QPushButton("🧩 New Flow")
        self.new_flow_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_flow_btn.setToolTip("Create a flow that chains methods, scripts and set-value actions")
        self.new_flow_btn.clicked.connect(self._create_flow)
        header_layout.addWidget(self.new_flow_btn)

        self.clear_all_btn = QPushButton("🗑 Clear All")
        self.clear_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_all_btn.clicked.connect(self.clear_all)
        header_layout.addWidget(self.clear_all_btn)

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
        """)

        self.clear_all_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {Colors.BORDER};
                color: {Colors.TEXT_MUTED};
                font-size: 11px;
                padding: 4px 8px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {Colors.ERROR_BG};
                color: {Colors.ERROR};
                border-color: {Colors.ERROR};
            }}
        """)

        self.new_flow_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {Colors.BORDER};
                color: {Colors.ACCENT};
                font-size: 11px;
                padding: 4px 8px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {Colors.BG_HOVER};
                border-color: {Colors.ACCENT};
            }}
        """)

    def add_favorite(self, node_id: str, display_name: str, node_type: NodeType,
                     server_url: str = "", server_name: str = "", args: list = None,
                     browse_path: list = None):
        """Add a node to favorites."""
        # Check if already exists (skip for methods, scripts and writes so we can
        # have duplicates with different args / values).
        if node_type not in (NodeType.METHOD, NodeType.SCRIPT, NodeType.WRITE):
            for card in self._cards:
                if card.fav_item.node_id == node_id and card.fav_item.node_type == node_type:
                    return

        write_value = ""
        write_data_type = ""
        if node_type == NodeType.WRITE and args:
            # The shared pipeline carries [value, data_type] in args.
            write_value = str(args[0]) if len(args) > 0 else ""
            write_data_type = str(args[1]) if len(args) > 1 else ""

        item = FavoriteItem(
            display_name=display_name,
            node_id=node_id,
            node_type=node_type,
            server_url=server_url,
            server_name=server_name,
            input_args=args or [],
            write_value=write_value,
            write_data_type=write_data_type,
            browse_path=browse_path or [],
        )
        self._add_card(item)
        self._save_favorites()

    def update_browse_path(self, item_id: str, browse_path: list, node_id: str = ""):
        """Store/refresh the resolved browse path (and node id) for a favorite.

        Used to self-heal older favorites and to keep node ids current after a
        server restart reassigns them.
        """
        changed = False
        for card in self._cards:
            if card.fav_item.id == item_id:
                if browse_path and card.fav_item.browse_path != browse_path:
                    card.fav_item.browse_path = browse_path
                    changed = True
                if node_id and card.fav_item.node_id != node_id:
                    card.fav_item.node_id = node_id
                    changed = True
                break
        if changed:
            self._save_favorites()

    def clear_all(self):
        """Remove all favorites."""
        for card in self._cards:
            self.list_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()
        self._save_favorites()

    def _add_card(self, item: FavoriteItem):
        card = FavoriteCard(item)
        card.clicked.connect(self.favorite_clicked.emit)
        card.execute_requested.connect(self.favorite_execute.emit)
        card.remove_requested.connect(self._remove_favorite)
        card.rename_requested.connect(self._rename_favorite)
        card.edit_requested.connect(self._edit_flow)
        self._cards.append(card)
        self.list_layout.insertWidget(self.list_layout.count() - 1, card)

    def _remove_favorite(self, item: FavoriteItem):
        for card in self._cards:
            if card.fav_item.id == item.id:
                self._cards.remove(card)
                card.deleteLater()
                break
        self._save_favorites()

    def _rename_favorite(self, item: FavoriteItem):
        """Show rename dialog and update the card."""
        from PyQt6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Favorite",
            "Enter a new name:",
            text=item.display_name,
        )
        if ok and new_name.strip():
            item.display_name = new_name.strip()
            # Rebuild the card
            for card in self._cards:
                if card.fav_item.id == item.id:
                    pos = self.list_layout.indexOf(card)
                    self._cards.remove(card)
                    card.deleteLater()
                    new_card = FavoriteCard(item)
                    new_card.clicked.connect(self.favorite_clicked.emit)
                    new_card.execute_requested.connect(self.favorite_execute.emit)
                    new_card.remove_requested.connect(self._remove_favorite)
                    new_card.rename_requested.connect(self._rename_favorite)
                    new_card.edit_requested.connect(self._edit_flow)
                    self._cards.insert(
                        next((i for i, c in enumerate(self._cards)
                              if self.list_layout.indexOf(c) > pos), len(self._cards)),
                        new_card
                    )
                    self.list_layout.insertWidget(pos, new_card)
                    break
            self._save_favorites()

    def add_script_favorite(self, script_path: str, display_name: str, args: list = None, script_content: str = ""):
        """Add a Python script to favorites."""
        # Use filename as node_id for better display instead of full path
        import os
        node_id = os.path.basename(script_path)
        
        # Allow duplicates for scripts so no return here.
        
        # Read script content if not provided
        if not script_content:
            try:
                with open(script_path, "r", encoding="utf-8") as f:
                    script_content = f.read()
            except Exception:
                pass

        item = FavoriteItem(
            display_name=display_name,
            node_id=node_id,
            node_type=NodeType.SCRIPT,
            server_url="",
            server_name="",
            input_args=args or [],
            script_content=script_content,
        )
        self._add_card(item)
        self._save_favorites()

    def _save_favorites(self):
        data = [card.fav_item.to_dict() for card in self._cards]
        try:
            with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _runnable_favorites(self) -> list[FavoriteItem]:
        """Favorites that can be used as flow steps (methods, scripts, set-values)."""
        return [
            card.fav_item for card in self._cards
            if card.fav_item.node_type in (NodeType.METHOD, NodeType.SCRIPT, NodeType.WRITE)
        ]

    def _create_flow(self):
        """Open the flow editor to build a new flow from existing favorites."""
        from app.dialogs.flow_dialog import FlowDialog

        available = self._runnable_favorites()
        if not available:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "No actions yet",
                "Add at least one method, script or set-value to your favorites first.\n"
                "Those become the building blocks of a flow.",
            )
            return

        dialog = FlowDialog(available, parent=self)
        if dialog.exec():
            name, steps = dialog.get_result()
            if name and steps:
                item = FavoriteItem(
                    display_name=name,
                    node_id="",
                    node_type=NodeType.FLOW,
                    flow_steps=steps,
                )
                self._add_card(item)
                self._save_favorites()

    def _edit_flow(self, item: FavoriteItem):
        """Open the flow editor to modify an existing flow."""
        from app.dialogs.flow_dialog import FlowDialog

        available = self._runnable_favorites()
        dialog = FlowDialog(available, parent=self, flow=item)
        if dialog.exec():
            name, steps = dialog.get_result()
            item.display_name = name or item.display_name
            item.flow_steps = steps
            # Rebuild the card in place.
            for card in self._cards:
                if card.fav_item.id == item.id:
                    pos = self.list_layout.indexOf(card)
                    self._cards.remove(card)
                    card.deleteLater()
                    new_card = FavoriteCard(item)
                    new_card.clicked.connect(self.favorite_clicked.emit)
                    new_card.execute_requested.connect(self.favorite_execute.emit)
                    new_card.remove_requested.connect(self._remove_favorite)
                    new_card.rename_requested.connect(self._rename_favorite)
                    new_card.edit_requested.connect(self._edit_flow)
                    self._cards.insert(min(pos, len(self._cards)), new_card)
                    self.list_layout.insertWidget(pos, new_card)
                    break
            self._save_favorites()

    def save(self):
        """Public hook to persist favorites (e.g. on app close)."""
        self._save_favorites()

    def _load_favorites(self):
        try:
            if not os.path.exists(FAVORITES_FILE):
                return
            with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return

        needs_save = False
        for item_data in data:
            # Load each favorite independently so one bad/legacy entry can't
            # wipe the whole list on startup.
            try:
                item = FavoriteItem.from_dict(item_data)
                # Upgrade old script favorites
                if item.node_type == NodeType.SCRIPT and not item.script_content:
                    if os.path.exists(item.node_id):
                        try:
                            with open(item.node_id, "r", encoding="utf-8") as sf:
                                item.script_content = sf.read()
                            item.node_id = os.path.basename(item.node_id)
                            needs_save = True
                        except Exception:
                            pass
                self._add_card(item)
            except Exception:
                continue
        if needs_save:
            self._save_favorites()
