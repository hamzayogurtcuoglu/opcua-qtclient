"""3D Scene Builder panel.

Hosts a three.js scene inside a ``QWebEngineView`` and drives it from Python
over a ``QWebChannel`` bridge. Python remains the single source of truth for the
scene model and for all OPC UA traffic; the web view is purely a renderer/input
surface.

Layout:  [ palette ] [ 3D view ] [ properties ]
Top bar:  name · Design/Run · Save · Load · Clear
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Callable, Optional

from PyQt6.QtCore import Qt, QObject, QUrl, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QFormLayout, QDoubleSpinBox, QComboBox, QFrame, QFileDialog, QMessageBox,
    QColorDialog, QButtonGroup,
)

from app.theme import Colors
from app.widgets.scene3d.model import (
    Scene3DModel, Object3DConfig, SHAPES, BINDINGS, DRIVES,
)

_WEB_DIR = os.path.join(os.path.dirname(__file__), "web")

_PALETTE = [
    ("box", "⬛ Box"),
    ("cylinder", "🛢 Cylinder"),
    ("sphere", "⚪ Sphere"),
    ("cone", "🔺 Cone"),
]


class _Bridge(QObject):
    """QWebChannel object exposed to JavaScript as ``bridge``."""

    toScene = pyqtSignal(str)  # Python -> JS (JSON command)

    def __init__(self, panel: "Scene3DPanel"):
        super().__init__()
        self._panel = panel

    @pyqtSlot()
    def onReady(self):
        self._panel._on_web_ready()

    @pyqtSlot(str)
    def onObjectSelected(self, obj_id: str):
        self._panel._on_object_selected(obj_id)

    @pyqtSlot(str)
    def onObjectClicked(self, obj_id: str):
        self._panel._on_object_clicked(obj_id)


class Scene3DPanel(QWidget):
    """Self-contained 3D scene builder + runtime."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._client = None
        self._node_picker: Optional[Callable[[], Optional[dict]]] = None
        self._objects: list[Object3DConfig] = []
        self._selected: Optional[Object3DConfig] = None
        self._design = True
        self._ready = False
        self._pending: list[str] = []
        self._timers: dict[str, QTimer] = {}
        self._loading_props = False
        self._setup_ui()

    # ── public wiring ─────────────────────────────────────────────────────
    def set_client(self, client):
        self._client = client
        connected = bool(client and getattr(client, "is_connected", False))
        self._status(
            "Connected — ready to run" if connected else "No active connection"
        )

    def set_node_picker(self, picker: Callable[[], Optional[dict]]):
        self._node_picker = picker

    # ── UI ────────────────────────────────────────────────────────────────
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)
        root.addLayout(self._build_topbar())

        body = QHBoxLayout()
        body.setSpacing(8)
        body.addWidget(self._build_palette())

        self.view = QWebEngineView()
        self.view.setMinimumSize(560, 420)
        self._channel = QWebChannel()
        self._bridge = _Bridge(self)
        self._channel.registerObject("bridge", self._bridge)
        self.view.page().setWebChannel(self._channel)
        self.view.setUrl(QUrl.fromLocalFile(os.path.join(_WEB_DIR, "index.html")))
        body.addWidget(self.view, 1)

        body.addWidget(self._build_properties())
        root.addLayout(body, 1)

        self.status_label = QLabel("No active connection")
        self.status_label.setStyleSheet(f"color:{Colors.TEXT_MUTED}; font-size:11px;")
        root.addWidget(self.status_label)

        self._refresh_mode_ui()

    def _build_topbar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.name_edit = QLineEdit("My 3D Scene")
        self.name_edit.setMaximumWidth(220)
        bar.addWidget(QLabel("🧊"))
        bar.addWidget(self.name_edit)
        bar.addStretch(1)

        self.design_btn = QPushButton("✎ Design")
        self.run_btn = QPushButton("▶ Run")
        grp = QButtonGroup(self)
        for b in (self.design_btn, self.run_btn):
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            grp.addButton(b)
        self.design_btn.setChecked(True)
        self.design_btn.clicked.connect(lambda: self._set_mode(True))
        self.run_btn.clicked.connect(lambda: self._set_mode(False))
        bar.addWidget(self.design_btn)
        bar.addWidget(self.run_btn)

        sep = QLabel("|")
        sep.setStyleSheet(f"color:{Colors.BORDER_LIGHT};")
        bar.addWidget(sep)

        for text, slot in (("⬆ Save", self._on_save), ("⬇ Load", self._on_load),
                           ("🗑 Clear", self._on_clear)):
            b = QPushButton(text)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            bar.addWidget(b)
        return bar

    def _build_palette(self) -> QWidget:
        panel = QFrame()
        panel.setFixedWidth(150)
        v = QVBoxLayout(panel)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)
        title = QLabel("SHAPES")
        title.setStyleSheet(f"color:{Colors.TEXT_MUTED}; font-size:10px; font-weight:800;")
        v.addWidget(title)
        self._palette_buttons = []
        for shape, label in _PALETTE:
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("text-align:left; padding:8px 10px;")
            btn.clicked.connect(lambda _=False, s=shape: self._add_object(s))
            v.addWidget(btn)
            self._palette_buttons.append(btn)
        v.addStretch(1)
        hint = QLabel("Add a shape, position it,\nthen bind an OPC UA node →")
        hint.setStyleSheet(f"color:{Colors.TEXT_MUTED}; font-size:10px;")
        hint.setWordWrap(True)
        v.addWidget(hint)
        return panel

    def _build_properties(self) -> QWidget:
        panel = QFrame()
        panel.setFixedWidth(280)
        v = QVBoxLayout(panel)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)
        title = QLabel("PROPERTIES")
        title.setStyleSheet(f"color:{Colors.TEXT_MUTED}; font-size:10px; font-weight:800;")
        v.addWidget(title)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(6)

        self.p_title = QLineEdit()
        self.p_title.textChanged.connect(lambda t: self._set_attr("title", t))
        form.addRow("Title", self.p_title)

        self.p_shape = QComboBox()
        self.p_shape.addItems(SHAPES)
        self.p_shape.currentTextChanged.connect(lambda t: self._set_attr("shape", t))
        form.addRow("Shape", self.p_shape)

        self.p_color = QPushButton("Pick color")
        self.p_color.clicked.connect(self._pick_color)
        form.addRow("Color", self.p_color)

        self.p_x = self._spin(-1000, 1000, 0.0)
        self.p_y = self._spin(-1000, 1000, 0.5)
        self.p_z = self._spin(-1000, 1000, 0.0)
        self.p_size = self._spin(0.1, 100, 1.0)
        self.p_x.valueChanged.connect(lambda v: self._set_attr("x", v))
        self.p_y.valueChanged.connect(lambda v: self._set_attr("y", v))
        self.p_z.valueChanged.connect(lambda v: self._set_attr("z", v))
        self.p_size.valueChanged.connect(lambda v: self._set_attr("size", v))
        pos_row = QHBoxLayout()
        for w in (self.p_x, self.p_y, self.p_z):
            pos_row.addWidget(w)
        pos_wrap = QWidget(); pos_wrap.setLayout(pos_row)
        form.addRow("X / Y / Z", pos_wrap)
        form.addRow("Size", self.p_size)

        self.p_node = QLineEdit()
        self.p_node.setPlaceholderText("ns=2;i=5")
        self.p_node.textChanged.connect(lambda t: self._set_attr("node_id", t.strip()))
        form.addRow("Node ID", self.p_node)

        self.pick_btn = QPushButton("⤓ Use selected node")
        self.pick_btn.clicked.connect(self._use_selected_node)
        form.addRow("", self.pick_btn)

        self.p_binding = QComboBox()
        self.p_binding.addItems(BINDINGS)  # read | call | write
        self.p_binding.currentTextChanged.connect(self._on_binding_changed)
        form.addRow("Binding", self.p_binding)

        self.p_drive = QComboBox()
        self.p_drive.addItems(DRIVES)  # color | scaleY | rotateY | posY | visible
        self.p_drive.currentTextChanged.connect(lambda t: self._set_attr("drive", t))
        form.addRow("Drives", self.p_drive)

        self.p_min = self._spin(-1e9, 1e9, 0.0)
        self.p_max = self._spin(-1e9, 1e9, 100.0)
        self.p_min.valueChanged.connect(lambda v: self._set_attr("min_value", v))
        self.p_max.valueChanged.connect(lambda v: self._set_attr("max_value", v))
        form.addRow("Min", self.p_min)
        form.addRow("Max", self.p_max)

        self.p_write = QLineEdit()
        self.p_write.setPlaceholderText("value on click (write)")
        self.p_write.textChanged.connect(lambda t: self._set_attr("write_value", t))
        form.addRow("Write", self.p_write)

        self.p_args = QLineEdit()
        self.p_args.setPlaceholderText("arg1, arg2 (method)")
        self.p_args.textChanged.connect(self._on_args_changed)
        form.addRow("Args", self.p_args)

        v.addLayout(form)

        self.delete_btn = QPushButton("🗑 Delete object")
        self.delete_btn.clicked.connect(self._delete_selected)
        v.addWidget(self.delete_btn)
        v.addStretch(1)
        self._props_panel = panel
        self._set_props_enabled(False)
        return panel

    def _spin(self, lo, hi, val) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setDecimals(2)
        s.setSingleStep(0.5)
        s.setValue(val)
        return s

    # ── object lifecycle ──────────────────────────────────────────────────
    def _add_object(self, shape: str):
        if not self._design:
            return
        cfg = Object3DConfig(shape=shape, title=shape.capitalize())
        self._objects.append(cfg)
        self._selected = cfg
        self._push_scene()
        self._send({"type": "select", "id": cfg.id})
        self._load_props(cfg)

    def _delete_selected(self):
        if self._selected is None:
            return
        self._objects = [o for o in self._objects if o.id != self._selected.id]
        self._selected = None
        self._push_scene()
        self._load_props(None)

    def _find(self, obj_id: str) -> Optional[Object3DConfig]:
        return next((o for o in self._objects if o.id == obj_id), None)

    # ── properties binding ────────────────────────────────────────────────
    def _set_attr(self, name: str, value):
        if self._loading_props or self._selected is None:
            return
        setattr(self._selected, name, value)
        self._push_scene()

    def _on_binding_changed(self, text: str):
        self._set_attr("binding", text)
        self._update_field_states()

    def _on_args_changed(self, text: str):
        if self._loading_props or self._selected is None:
            return
        parts = [p.strip() for p in text.split(",") if p.strip()]
        self._selected.method_args = [self._coerce(p) for p in parts]

    def _pick_color(self):
        if self._selected is None:
            return
        col = QColorDialog.getColor(QColor(self._selected.color), self, "Object color")
        if col.isValid():
            self._set_attr("color", col.name())
            self._style_color_btn(col.name())

    def _style_color_btn(self, hexcol: str):
        self.p_color.setStyleSheet(f"background:{hexcol}; color:#fff; padding:6px;")

    def _use_selected_node(self):
        if self._selected is None:
            return
        if self._node_picker is None:
            self._status("No node selected in the address tree")
            return
        info = self._node_picker()
        if not info or not info.get("node_id"):
            self._status("Select a node in the address tree first")
            return
        self._selected.node_id = info["node_id"]
        self._selected.data_type = info.get("data_type", "")
        self._selected.parent_id = info.get("parent_id", "")
        self._load_props(self._selected)
        self._push_scene()
        self._status(f"Bound to {info['node_id']}")

    def _load_props(self, cfg: Optional[Object3DConfig]):
        self._loading_props = True
        if cfg is None:
            self._set_props_enabled(False)
            for w in (self.p_title, self.p_node, self.p_write, self.p_args):
                w.clear()
            self._loading_props = False
            return
        self._set_props_enabled(True)
        self.p_title.setText(cfg.title)
        self.p_shape.setCurrentText(cfg.shape)
        self.p_x.setValue(cfg.x)
        self.p_y.setValue(cfg.y)
        self.p_z.setValue(cfg.z)
        self.p_size.setValue(cfg.size)
        self.p_node.setText(cfg.node_id)
        self.p_binding.setCurrentText(cfg.binding)
        self.p_drive.setCurrentText(cfg.drive)
        self.p_min.setValue(cfg.min_value)
        self.p_max.setValue(cfg.max_value)
        self.p_write.setText(cfg.write_value)
        self.p_args.setText(", ".join(str(a) for a in cfg.method_args))
        self._style_color_btn(cfg.color)
        self._loading_props = False
        self._update_field_states()

    def _update_field_states(self):
        if self._selected is None:
            return
        is_read = self._selected.binding == "read"
        is_call = self._selected.binding == "call"
        is_write = self._selected.binding == "write"
        self.p_drive.setEnabled(is_read)
        self.p_min.setEnabled(is_read)
        self.p_max.setEnabled(is_read)
        self.p_write.setEnabled(is_write)
        self.p_args.setEnabled(is_call)

    def _set_props_enabled(self, on: bool):
        for w in (self.p_title, self.p_shape, self.p_color, self.p_x, self.p_y,
                  self.p_z, self.p_size, self.p_node, self.pick_btn, self.p_binding,
                  self.p_drive, self.p_min, self.p_max, self.p_write, self.p_args,
                  self.delete_btn):
            w.setEnabled(on)

    @staticmethod
    def _coerce(text: str):
        for caster in (int, float):
            try:
                return caster(text)
            except ValueError:
                continue
        low = text.lower()
        if low in ("true", "false"):
            return low == "true"
        return text

    # ── bridge callbacks (from JS) ────────────────────────────────────────
    def _on_web_ready(self):
        self._ready = True
        for msg in self._pending:
            self._bridge.toScene.emit(msg)
        self._pending.clear()
        self._push_scene()

    def _on_object_selected(self, obj_id: str):
        cfg = self._find(obj_id)
        self._selected = cfg
        self._load_props(cfg)

    def _on_object_clicked(self, obj_id: str):
        if self._design:
            return
        cfg = self._find(obj_id)
        if cfg is None or not cfg.node_id:
            return
        if not self._client or not getattr(self._client, "is_connected", False):
            self._status("⚠ Not connected")
            return
        if cfg.binding == "call":
            asyncio.ensure_future(self._call_async(cfg))
        elif cfg.binding == "write":
            value = self._coerce(cfg.write_value)
            asyncio.ensure_future(
                self._client.write_value(cfg.node_id, value, cfg.data_type)
            )
            self._status(f"Wrote {value} → {cfg.node_id}")

    async def _call_async(self, cfg: Object3DConfig):
        parent_id = cfg.parent_id or await self._client.get_parent_node_id(cfg.node_id)
        result = await self._client.call_method(parent_id, cfg.node_id, list(cfg.method_args))
        self._status(f"Called {cfg.title} → {result}")

    # ── mode + runtime ────────────────────────────────────────────────────
    def _set_mode(self, design: bool):
        self._design = design
        self.design_btn.setChecked(design)
        self.run_btn.setChecked(not design)
        self._send({"type": "mode", "design": design})
        self._refresh_mode_ui()
        if design:
            self._stop_runtime()
        else:
            self._start_runtime()

    def _refresh_mode_ui(self):
        for b in getattr(self, "_palette_buttons", []):
            b.setEnabled(self._design)
        self._props_panel.setVisible(self._design)

    def _start_runtime(self):
        if not self._client or not getattr(self._client, "is_connected", False):
            self._status("⚠ Connect to a server before running")
            return
        self._stop_runtime()
        count = 0
        for cfg in self._objects:
            if cfg.binding == "read" and cfg.node_id:
                timer = QTimer(self)
                timer.setInterval(500)
                timer.timeout.connect(lambda c=cfg: self._poll(c))
                timer.start()
                self._timers[cfg.id] = timer
                count += 1
        self._status(f"▶ Running — polling {count} node(s)")

    def _stop_runtime(self):
        for t in self._timers.values():
            t.stop()
            t.deleteLater()
        self._timers.clear()

    def _poll(self, cfg: Object3DConfig):
        if self._client:
            asyncio.ensure_future(self._poll_async(cfg))

    async def _poll_async(self, cfg: Object3DConfig):
        value = await self._client.poll_value(cfg.node_id)
        if value is not None:
            self._send({"type": "values", "values": {cfg.id: value}})

    # ── scene sync ────────────────────────────────────────────────────────
    def _push_scene(self):
        self._send({
            "type": "scene",
            "design": self._design,
            "objects": [o.to_dict() for o in self._objects],
        })

    def _send(self, cmd: dict):
        msg = json.dumps(cmd)
        if self._ready:
            self._bridge.toScene.emit(msg)
        else:
            self._pending.append(msg)

    # ── save / load ───────────────────────────────────────────────────────
    def _on_save(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save 3D Scene",
            os.path.expanduser(f"~/{self.name_edit.text() or 'scene'}.json"),
            "Scene (*.json)",
        )
        if not path:
            return
        model = Scene3DModel(name=self.name_edit.text() or "Scene", objects=self._objects)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(model.to_dict(), f, indent=2)
            self._status(f"Saved → {os.path.basename(path)}")
        except OSError as e:
            QMessageBox.warning(self, "Save failed", str(e))

    def _on_load(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load 3D Scene", os.path.expanduser("~"), "Scene (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            model = Scene3DModel.from_dict(data)
        except (OSError, ValueError, json.JSONDecodeError) as e:
            QMessageBox.warning(self, "Load failed", str(e))
            return
        self.name_edit.setText(model.name)
        self._objects = model.objects
        self._selected = None
        self._push_scene()
        self._load_props(None)
        self._status(f"Loaded {len(model.objects)} object(s)")

    def _on_clear(self):
        if QMessageBox.question(self, "Clear scene", "Remove all objects?") \
                == QMessageBox.StandardButton.Yes:
            self._objects = []
            self._selected = None
            self._push_scene()
            self._load_props(None)

    def _status(self, text: str):
        self.status_label.setText(text)
