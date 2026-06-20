"""Dialog for building/editing a Flow — an ordered chain of favorite actions."""

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QInputDialog,
    QDialogButtonBox, QMessageBox,
)

from app.models import FavoriteItem, NodeType
from app.theme import Colors


_KIND_FOR_TYPE = {
    NodeType.METHOD: "method",
    NodeType.SCRIPT: "script",
    NodeType.WRITE: "write",
}

_KIND_ICON = {
    "method": "\u2699",   # gear
    "script": "\u25b6",   # play
    "write": "\u270f",    # pencil
    "wait": "\u23f1",     # stopwatch
}


def favorite_to_step(fav: FavoriteItem) -> dict:
    """Build a self-contained flow step dict from an existing favorite."""
    kind = _KIND_FOR_TYPE.get(fav.node_type, "method")
    return {
        "kind": kind,
        "display_name": fav.display_name,
        "node_id": fav.node_id,
        "server_url": fav.server_url,
        "server_name": fav.server_name,
        "input_args": list(fav.input_args or []),
        "script_content": fav.script_content,
        "write_value": fav.write_value,
        "write_data_type": fav.write_data_type,
        "wait_seconds": 0.0,
    }


def wait_step(seconds: float) -> dict:
    """Build a 'wait' flow step."""
    return {
        "kind": "wait",
        "display_name": f"Wait {seconds:g}s",
        "node_id": "",
        "server_url": "",
        "server_name": "",
        "input_args": [],
        "script_content": "",
        "write_value": "",
        "write_data_type": "",
        "wait_seconds": float(seconds),
    }


def step_label(step: dict) -> str:
    """Human readable one-line label for a flow step."""
    kind = step.get("kind", "")
    icon = _KIND_ICON.get(kind, "\u2022")
    name = step.get("display_name") or step.get("node_id") or kind
    if kind == "wait":
        return f"{icon}  Wait {step.get('wait_seconds', 0):g}s"
    tag = kind.capitalize()
    if kind == "write":
        return f"{icon}  {name}  \u2192 {step.get('write_value', '')}"
    return f"{icon}  [{tag}] {name}"


class FlowDialog(QDialog):
    """Editor to assemble an ordered flow of favorite actions + waits."""

    def __init__(self, available: list[FavoriteItem],
                 parent: Optional[object] = None,
                 flow: Optional[FavoriteItem] = None):
        super().__init__(parent)
        self._available = available
        self._flow = flow
        self._setup_ui()
        if flow:
            self.name_input.setText(flow.display_name)
            for step in (flow.flow_steps or []):
                self._append_step(dict(step))

    # ── UI ────────────────────────────────────────────────────────────────
    def _setup_ui(self):
        self.setWindowTitle("Edit Flow" if self._flow else "New Flow")
        self.setMinimumSize(680, 480)
        self.setStyleSheet(f"QDialog {{ background-color: {Colors.BG_DARK}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        title = QLabel("\U0001f9e9  Flow Builder")
        title.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {Colors.TEXT_PRIMARY}; background: transparent;"
        )
        layout.addWidget(title)

        subtitle = QLabel(
            "Chain method calls, scripts and set-value actions. Steps run top-to-bottom, "
            "each waiting for the previous one to finish."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(
            f"font-size: 12px; color: {Colors.TEXT_SECONDARY}; background: transparent;"
        )
        layout.addWidget(subtitle)

        # Name
        name_row = QHBoxLayout()
        name_label = QLabel("Flow name:")
        name_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        name_row.addWidget(name_label)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Start sequence")
        self.name_input.setStyleSheet(self._input_style())
        name_row.addWidget(self.name_input, 1)
        layout.addLayout(name_row)

        # Two columns: available actions | flow steps
        cols = QHBoxLayout()
        cols.setSpacing(14)

        # Left: available actions
        left = QVBoxLayout()
        left.setSpacing(6)
        left.addWidget(self._section_label("Available actions"))
        self.available_list = QListWidget()
        self.available_list.setStyleSheet(self._list_style())
        for fav in self._available:
            label = step_label(favorite_to_step(fav))
            li = QListWidgetItem(label)
            li.setData(Qt.ItemDataRole.UserRole, fav)
            self.available_list.addItem(li)
        self.available_list.itemDoubleClicked.connect(lambda _: self._add_selected())
        left.addWidget(self.available_list, 1)

        add_btn = QPushButton("Add \u2192")
        add_btn.setStyleSheet(self._btn_style(primary=True))
        add_btn.clicked.connect(self._add_selected)
        left.addWidget(add_btn)

        wait_btn = QPushButton("\u23f1 Add Wait\u2026")
        wait_btn.setStyleSheet(self._btn_style())
        wait_btn.clicked.connect(self._add_wait)
        left.addWidget(wait_btn)

        cols.addLayout(left, 1)

        # Right: flow steps
        right = QVBoxLayout()
        right.setSpacing(6)
        right.addWidget(self._section_label("Flow steps (in order)"))
        self.steps_list = QListWidget()
        self.steps_list.setStyleSheet(self._list_style())
        right.addWidget(self.steps_list, 1)

        controls = QHBoxLayout()
        for text, slot in (
            ("\u25b2 Up", self._move_up),
            ("\u25bc Down", self._move_down),
            ("\u2715 Remove", self._remove_step),
        ):
            b = QPushButton(text)
            b.setStyleSheet(self._btn_style())
            b.clicked.connect(slot)
            controls.addWidget(b)
        right.addLayout(controls)

        cols.addLayout(right, 1)
        layout.addLayout(cols, 1)

        # OK / Cancel
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {Colors.TEXT_SECONDARY}; background: transparent;"
        )
        return lbl

    # ── Step operations ───────────────────────────────────────────────────
    def _append_step(self, step: dict):
        li = QListWidgetItem(step_label(step))
        li.setData(Qt.ItemDataRole.UserRole, step)
        self.steps_list.addItem(li)

    def _add_selected(self):
        item = self.available_list.currentItem()
        if item is None:
            return
        fav: FavoriteItem = item.data(Qt.ItemDataRole.UserRole)
        self._append_step(favorite_to_step(fav))

    def _add_wait(self):
        seconds, ok = QInputDialog.getDouble(
            self, "Add Wait", "Wait duration (seconds):", 1.0, 0.0, 86400.0, 1
        )
        if ok:
            self._append_step(wait_step(seconds))

    def _move_up(self):
        row = self.steps_list.currentRow()
        if row > 0:
            item = self.steps_list.takeItem(row)
            self.steps_list.insertItem(row - 1, item)
            self.steps_list.setCurrentRow(row - 1)

    def _move_down(self):
        row = self.steps_list.currentRow()
        if 0 <= row < self.steps_list.count() - 1:
            item = self.steps_list.takeItem(row)
            self.steps_list.insertItem(row + 1, item)
            self.steps_list.setCurrentRow(row + 1)

    def _remove_step(self):
        row = self.steps_list.currentRow()
        if row >= 0:
            self.steps_list.takeItem(row)

    # ── Result ────────────────────────────────────────────────────────────
    def _on_accept(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Missing name", "Please enter a name for the flow.")
            return
        if self.steps_list.count() == 0:
            QMessageBox.warning(self, "No steps", "Add at least one step to the flow.")
            return
        self.accept()

    def get_result(self) -> tuple[str, list[dict]]:
        name = self.name_input.text().strip()
        steps = [
            self.steps_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.steps_list.count())
        ]
        return name, steps

    # ── Styles ────────────────────────────────────────────────────────────
    def _input_style(self) -> str:
        return f"""
            QLineEdit {{
                background-color: {Colors.BG_INPUT};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
                padding: 6px 8px;
                color: {Colors.TEXT_PRIMARY};
            }}
        """

    def _list_style(self) -> str:
        return f"""
            QListWidget {{
                background-color: {Colors.BG_INPUT};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
                color: {Colors.TEXT_PRIMARY};
                padding: 4px;
            }}
            QListWidget::item {{ padding: 5px; border-radius: 4px; }}
            QListWidget::item:selected {{
                background-color: {Colors.ACCENT};
                color: white;
            }}
        """

    def _btn_style(self, primary: bool = False) -> str:
        bg = Colors.ACCENT if primary else "transparent"
        color = "white" if primary else Colors.TEXT_PRIMARY
        return f"""
            QPushButton {{
                background-color: {bg};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                color: {color};
            }}
            QPushButton:hover {{
                border-color: {Colors.ACCENT};
                background-color: {Colors.BG_HOVER if not primary else Colors.ACCENT};
            }}
        """
