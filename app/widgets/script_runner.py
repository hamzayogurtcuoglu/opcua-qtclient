"""Script Runner Panel — load, inspect and run Python scripts with argument support."""

import ast
import os
import re
import subprocess
import sys
from typing import Optional

from PyQt6.QtCore import Qt, QProcess, QProcessEnvironment, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QFileDialog, QFrame, QSizePolicy, QComboBox, QAbstractItemView,
    QScrollArea,
)

from app.theme import Colors, theme_manager


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_argparse_args(script_path: str) -> list[dict]:
    """
    Run the script with --help and parse argparse output.
    Returns list of dicts: {name, dest, type, default, choices, help, required}
    """
    try:
        env = QProcessEnvironment.systemEnvironment()
        result = subprocess.run(
            [sys.executable, script_path, "--help"],
            capture_output=True,
            text=True,
            timeout=5,
            env=dict(os.environ),
        )
        output = result.stdout + result.stderr
        return _parse_help_output(output)
    except Exception:
        return []


def _parse_help_output(help_text: str) -> list[dict]:
    """Parse argparse --help output to extract arguments."""
    args = []
    # Normalize whitespace from wrapped lines: join continuation lines
    # Argparse wraps long help at ~78 chars; continuation lines start with many spaces
    normalized = re.sub(r"\n\s{20,}", " ", help_text)

    pattern = re.compile(
        r"^\s{2,4}(-\w)?,?\s*(--[\w\-]+)(?:\s+([A-Z][A-Z0-9_{}|,]+))?\s*(.*?)$",
        re.MULTILINE
    )
    for m in pattern.finditer(normalized):
        long_flag = m.group(2)
        metavar = m.group(3)
        description = m.group(4).strip()

        if not long_flag or long_flag in ("--help", "--version"):
            continue

        name = long_flag

        # Extract actual default from description: '(default: 4840)'
        default_match = re.search(r"\(default:\s*([^)]+)\)", description, re.IGNORECASE)
        actual_default = default_match.group(1).strip() if default_match else ""

        # Choices: {read,call,...} metavar → str type
        if metavar and metavar.startswith("{"):
            arg_type = "str"
            # Default for choices comes from actual_default or first choice
            if not actual_default:
                choices = metavar.strip("{}").split(",")
                actual_default = choices[0] if choices else ""
            default = actual_default
        elif metavar:
            mv = metavar.upper()
            if any(x in mv for x in ("PORT", "INT", "NUM", "COUNT", "SECOND", "TIMEOUT")):
                arg_type = "int"
                default = actual_default if actual_default else "0"
            elif any(x in mv for x in ("FLOAT", "RATE")):
                arg_type = "float"
                default = actual_default if actual_default else "0.0"
            else:
                arg_type = "str"
                default = actual_default
        else:
            # no metavar → check if it's a real bool flag or just inline choices
            bool_defaults = ("true", "false", "")
            if actual_default.lower() in bool_defaults:
                arg_type = "bool"
                default = actual_default.capitalize() if actual_default else "False"
            else:
                # Has a non-boolean default with no metavar → treat as str
                arg_type = "str"
                default = actual_default

        # Post-process: if default is True/False string and no real metavar, treat as bool
        if arg_type == "str" and default in ("True", "False") and not metavar:
            arg_type = "bool"
        # Clean up literal 'empty' from help strings like '(default: empty)'
        if default == "empty":
            default = ""

        args.append({
            "name": name,
            "dest": long_flag.lstrip("-").replace("-", "_"),
            "type": arg_type,
            "default": default,
            "help": description,
        })

    return args


def _parse_ast_args(script_path: str) -> list[dict]:
    """
    Parse Python script with AST to find main() function parameters.
    Returns list of dicts: {name, type, default}
    """
    try:
        with open(script_path, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
    except Exception:
        return []

    # Find main() or async def main()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "main":
            return _extract_func_params(node)

    return []


def _extract_func_params(func_node) -> list[dict]:
    """Extract parameters from an AST function definition."""
    args = func_node.args
    params = []

    # Build defaults list aligned to the end of args
    defaults = args.defaults
    n_args = len(args.args)
    n_defaults = len(defaults)
    padded_defaults = [None] * (n_args - n_defaults) + list(defaults)

    for i, arg in enumerate(args.args):
        if arg.arg in ("self", "cls"):
            continue

        # Annotation → type hint
        ann = arg.annotation
        if ann:
            if isinstance(ann, ast.Name):
                type_name = ann.id
            elif isinstance(ann, ast.Constant):
                type_name = str(ann.value)
            else:
                type_name = "str"
        else:
            type_name = "str"

        # Default value
        default_node = padded_defaults[i]
        if default_node is None:
            default_val = ""
        elif isinstance(default_node, ast.Constant):
            default_val = str(default_node.value)
        else:
            default_val = ""

        # Normalise type
        if type_name in ("bool",):
            arg_type = "bool"
        elif type_name in ("int",):
            arg_type = "int"
        elif type_name in ("float",):
            arg_type = "float"
        else:
            arg_type = "str"

        params.append({
            "name": f"--{arg.arg}",
            "dest": arg.arg,
            "type": arg_type,
            "default": default_val,
            "help": "",
        })

    return params


def detect_script_args(script_path: str) -> tuple[list[dict], str]:
    """
    Detect script arguments using argparse --help first, then AST fallback.
    Returns (args_list, method_used).
    """
    args = _parse_argparse_args(script_path)
    if args:
        return args, "argparse"

    args = _parse_ast_args(script_path)
    if args:
        return args, "ast"

    return [], "none"


# ─────────────────────────────────────────────────────────────────────────────
# ScriptRunnerPanel
# ─────────────────────────────────────────────────────────────────────────────

class ScriptRunnerPanel(QWidget):
    """Side panel for loading and running Python scripts."""

    # Emits (script_path, display_name, args_list, script_content) when user clicks Favorite
    add_to_favorites = pyqtSignal(str, str, list, str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._script_path: Optional[str] = None
        self._script_content: str = ""
        self._args_data: list[dict] = []
        self._process: Optional[QProcess] = None
        self._setup_ui()

    # ── UI Build ──────────────────────────────────────────────────────────────

    def _setup_ui(self):
        self.setMinimumWidth(280)
        self.setMaximumWidth(380)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Outer card frame
        self.card = QFrame()
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(12)

        # ── Header ──
        header = QHBoxLayout()
        self.icon_label = QLabel("▶")
        header.addWidget(self.icon_label)
        self.title_label = QLabel("Script Runner")
        header.addWidget(self.title_label)
        header.addStretch()
        card_layout.addLayout(header)

        # ── Load section ──
        self.load_section = QFrame()
        load_layout = QVBoxLayout(self.load_section)
        load_layout.setContentsMargins(10, 10, 10, 10)
        load_layout.setSpacing(8)

        # File picker row
        file_row = QHBoxLayout()
        self.load_btn = QPushButton("📂 Load Script")
        self.load_btn.setProperty("class", "primary")
        self.load_btn.setMinimumHeight(32)
        self.load_btn.clicked.connect(self._on_load_script)
        file_row.addWidget(self.load_btn, 1)
        load_layout.addLayout(file_row)

        # File name display
        self.file_label = QLabel("No script loaded")
        self.file_label.setWordWrap(True)
        load_layout.addWidget(self.file_label)

        card_layout.addWidget(self.load_section)

        # ── Separator label ──
        self.params_label = QLabel("Parameters")
        self.params_label.hide()
        card_layout.addWidget(self.params_label)

        # ── Arguments table ──
        self.args_table = QTableWidget(0, 3)
        self.args_table.setHorizontalHeaderLabels(["Parameter", "Type", "Value"])
        self.args_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.args_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.args_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.args_table.verticalHeader().setVisible(False)
        self.args_table.verticalHeader().setDefaultSectionSize(34)
        self.args_table.setMinimumHeight(80)
        self.args_table.setMaximumHeight(200)
        self.args_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked |
                                         QAbstractItemView.EditTrigger.SelectedClicked)
        self.args_table.hide()
        card_layout.addWidget(self.args_table)

        # Extra args (free text for unlisted flags)
        self.extra_args_label = QLabel("Extra arguments (optional)")
        self.extra_args_label.hide()

        from PyQt6.QtWidgets import QLineEdit
        self.extra_args_input = QLineEdit()
        self.extra_args_input.setPlaceholderText("e.g. --verbose --timeout 30")
        self.extra_args_input.hide()
        card_layout.addWidget(self.extra_args_label)
        card_layout.addWidget(self.extra_args_input)

        # ── Output section label ──
        self.output_label = QLabel("Output")
        card_layout.addWidget(self.output_label)

        # ── Output terminal ──
        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        self.output_box.setMinimumHeight(160)
        self.output_box.setPlaceholderText("Script output will appear here...")
        card_layout.addWidget(self.output_box, 1)

        # ── Control buttons ──
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(6)

        self.run_btn = QPushButton("▶  Run")
        self.run_btn.setProperty("class", "primary")
        self.run_btn.setMinimumHeight(34)
        self.run_btn.setMinimumWidth(90)
        self.run_btn.clicked.connect(self._on_run)
        self.run_btn.setEnabled(False)
        ctrl_row.addWidget(self.run_btn)

        self.stop_btn = QPushButton("⏹  Stop")
        self.stop_btn.setMinimumHeight(34)
        self.stop_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {Colors.ERROR};
                border-radius: 6px;
                color: {Colors.ERROR};
                font-weight: bold;
                padding: 6px 14px;
            }}
            QPushButton:hover {{
                background-color: {Colors.ERROR_BG};
            }}
            QPushButton:disabled {{
                border-color: {Colors.BORDER};
                color: {Colors.TEXT_MUTED};
            }}
        """)
        self.stop_btn.clicked.connect(self._on_stop)
        self.stop_btn.setEnabled(False)
        ctrl_row.addWidget(self.stop_btn)

        self.fav_btn = QPushButton("⭐ Favorite")
        self.fav_btn.setMinimumHeight(34)
        self.fav_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {Colors.NODE_METHOD};
                border-radius: 6px;
                color: {Colors.NODE_METHOD};
                font-weight: bold;
                padding: 6px 14px;
            }}
            QPushButton:hover {{
                background-color: {Colors.NODE_METHOD};
                color: white;
            }}
            QPushButton:disabled {{
                border-color: {Colors.BORDER};
                color: {Colors.TEXT_MUTED};
            }}
        """)
        self.fav_btn.clicked.connect(self._on_favorite)
        self.fav_btn.setEnabled(False)
        ctrl_row.addWidget(self.fav_btn)

        ctrl_row.addStretch()

        self.clear_btn = QPushButton("🗑")
        self.clear_btn.setFixedSize(34, 34)
        self.clear_btn.setToolTip("Clear output")
        self.clear_btn.clicked.connect(self._on_clear)
        ctrl_row.addWidget(self.clear_btn)

        card_layout.addLayout(ctrl_row)
        outer.addWidget(self.card)

        self.update_theme()
        theme_manager.theme_changed.connect(self.update_theme)

    def update_theme(self):
        self.card.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_DARK};
                border: 1px solid {Colors.BORDER};
                border-radius: 12px;
            }}
        """)
        
        self.icon_label.setStyleSheet(f"font-size: 16px; color: {Colors.SUCCESS}; background: transparent;")
        self.title_label.setStyleSheet(f"""
            font-size: 15px;
            font-weight: bold;
            color: {Colors.TEXT_PRIMARY};
            background: transparent;
        """)
        
        self.load_section.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
            }}
        """)

        # file_label styling is dependent on if script is loaded.
        if self._script_path:
            self.file_label.setStyleSheet(f"""
                font-size: 11px;
                color: {Colors.TEXT_PRIMARY};
                background: transparent;
            """)
        else:
            self.file_label.setStyleSheet(f"""
                font-size: 11px;
                color: {Colors.TEXT_MUTED};
                background: transparent;
            """)
            
        self.params_label.setStyleSheet(f"""
            font-size: 12px;
            font-weight: bold;
            color: {Colors.TEXT_SECONDARY};
            background: transparent;
        """)

        self.args_table.horizontalHeader().setStyleSheet(f"""
            QHeaderView::section {{
                background-color: {Colors.BG_SURFACE};
                color: {Colors.TEXT_SECONDARY};
                border: none;
                border-bottom: 1px solid {Colors.BORDER};
                padding: 4px;
                font-size: 11px;
            }}
        """)
        self.args_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                gridline-color: {Colors.BORDER};
            }}
            QTableWidget::item {{
                color: {Colors.TEXT_PRIMARY};
                padding: 2px 6px;
            }}
            QTableWidget::item:selected {{
                background-color: {Colors.BG_HOVER};
            }}
        """)
        
        self.extra_args_label.setStyleSheet(f"""
            font-size: 11px;
            color: {Colors.TEXT_SECONDARY};
            background: transparent;
        """)
        self.extra_args_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Colors.BG_INPUT};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
                color: {Colors.TEXT_PRIMARY};
                padding: 6px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {Colors.BORDER_FOCUS};
            }}
        """)
        
        self.output_label.setStyleSheet(f"""
            font-size: 12px;
            font-weight: bold;
            color: {Colors.TEXT_SECONDARY};
            background: transparent;
        """)
        self.output_box.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Colors.BG_DARKEST};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                padding: 8px;
                font-family: 'Menlo', 'Courier New', 'Courier';
                font-size: 11px;
                color: #a8d8a8;
            }}
        """)
        
        self.stop_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {Colors.ERROR};
                border-radius: 6px;
                color: {Colors.ERROR};
                font-weight: bold;
                padding: 6px 14px;
            }}
            QPushButton:hover {{
                background-color: {Colors.ERROR_BG};
            }}
            QPushButton:disabled {{
                border-color: {Colors.BORDER};
                color: {Colors.TEXT_MUTED};
            }}
        """)
        
        self.fav_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {Colors.NODE_METHOD};
                border-radius: 6px;
                color: {Colors.NODE_METHOD};
                font-weight: bold;
                padding: 6px 14px;
            }}
            QPushButton:hover {{
                background-color: {Colors.NODE_METHOD};
                color: white;
            }}
            QPushButton:disabled {{
                border-color: {Colors.BORDER};
                color: {Colors.TEXT_MUTED};
            }}
        """)
        
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
                color: {Colors.TEXT_MUTED};
                font-size: 14px;
            }}
            QPushButton:hover {{
                color: {Colors.TEXT_PRIMARY};
                border-color: {Colors.BORDER_LIGHT};
            }}
        """)
        
        if self._args_data:
            # We need to re-render combo boxes and re-style types in the args table
            saved_vals = []
            for i in range(self.args_table.rowCount()):
                val_widget = self.args_table.cellWidget(i, 2)
                if isinstance(val_widget, QComboBox):
                    saved_vals.append(val_widget.currentText())
                else:
                    saved_vals.append("")

            self._populate_args_table(self._args_data)

            # Restore combobox values
            for i in range(min(len(saved_vals), self.args_table.rowCount())):
                val_widget = self.args_table.cellWidget(i, 2)
                if isinstance(val_widget, QComboBox) and saved_vals[i]:
                    idx = val_widget.findText(saved_vals[i])
                    if idx >= 0:
                        val_widget.setCurrentIndex(idx)

    # ── Script Loading ────────────────────────────────────────────────────────

    def _on_load_script(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Python Script", "",
            "Python Files (*.py);;All Files (*)"
        )
        if not path:
            return

        self.load_script(path)

    def load_script(self, path: str, saved_args: list = None, script_content: str = "") -> bool:
        """Load a script file and populate arguments."""
        self._script_content = script_content
        
        # If we have content but the path doesn't exist (e.g. imported on another PC)
        # we write it to a temporary file to run it.
        if script_content and not os.path.exists(path):
            import tempfile
            fd, tmp_path = tempfile.mkstemp(suffix=".py", prefix="opcua_script_")
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(script_content)
            path = tmp_path
            
        if not os.path.exists(path):
            self._append_output(f"[Error] File not found: {path}\n", error=True)
            return False

        # If we don't have content, read it now so we can save it to favorites later
        if not self._script_content:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._script_content = f.read()
            except Exception:
                pass

        self._script_path = path
        filename = os.path.basename(path)
        self.file_label.setText(f"📄 {filename}")
        self.update_theme()
        self.run_btn.setEnabled(True)
        self.fav_btn.setEnabled(True)

        # Detect arguments
        self._load_args(path)
        self._append_output(f"[Loaded] {path}\n")

        # Restore saved arguments if any
        if saved_args and self._args_data:
            for i, val in enumerate(saved_args):
                if i < self.args_table.rowCount():
                    combo = self.args_table.cellWidget(i, 2)
                    if isinstance(combo, QComboBox):
                        idx = combo.findText(str(val))
                        if idx >= 0:
                            combo.setCurrentIndex(idx)
                    else:
                        item = self.args_table.item(i, 2)
                        if item:
                            item.setText(str(val))

        return True

    def _load_args(self, path: str):
        """Detect and display script arguments."""
        args, method = detect_script_args(path)
        self._args_data = args

        if args:
            self.params_label.show()
            self.args_table.show()
            self.extra_args_label.show()
            self.extra_args_input.show()
            self._populate_args_table(args)
            self._append_output(f"[Info] Found {len(args)} parameter(s) via {method}\n")
        else:
            self.params_label.hide()
            self.args_table.hide()
            self._args_data = []
            self.extra_args_label.show()
            self.extra_args_input.show()
            self._append_output("[Info] No named parameters found. Use extra args box below if needed.\n")

    def _populate_args_table(self, args: list[dict]):
        self.args_table.setRowCount(len(args))
        for i, arg in enumerate(args):
            # Name (read-only)
            name_item = QTableWidgetItem(arg["name"])
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            name_item.setToolTip(arg.get("help", ""))
            self.args_table.setItem(i, 0, name_item)

            # Type badge (read-only)
            type_item = QTableWidgetItem(arg["type"])
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            type_color = {
                "str": Colors.NODE_VARIABLE,
                "int": Colors.NODE_METHOD,
                "float": Colors.WARNING,
                "bool": Colors.SUCCESS,
            }.get(arg["type"], Colors.TEXT_SECONDARY)
            type_item.setForeground(__import__("PyQt6.QtGui", fromlist=["QColor"]).QColor(type_color))
            self.args_table.setItem(i, 1, type_item)

            # Value widget
            if arg["type"] == "bool":
                combo = QComboBox()
                combo.addItems(["False", "True"])
                combo.setStyleSheet(f"""
                    QComboBox {{
                        background-color: {Colors.BG_INPUT};
                        color: {Colors.TEXT_PRIMARY};
                        border: 1px solid {Colors.BORDER};
                        border-radius: 4px;
                        padding: 2px 6px;
                    }}
                """)
                if arg.get("default", "").lower() == "true":
                    combo.setCurrentText("True")
                self.args_table.setCellWidget(i, 2, combo)
            else:
                val_item = QTableWidgetItem(str(arg.get("default", "")))
                self.args_table.setItem(i, 2, val_item)

    # ── Run / Stop ────────────────────────────────────────────────────────────

    def _build_command(self) -> list[str]:
        """Build the subprocess command list from current values."""
        cmd = [sys.executable, self._script_path]

        for i, arg in enumerate(self._args_data):
            name = arg["name"]
            arg_type = arg["type"]

            combo = self.args_table.cellWidget(i, 2)
            if combo:
                val = combo.currentText()
            else:
                item = self.args_table.item(i, 2)
                val = item.text() if item else ""

            if arg_type == "bool":
                if val == "True":
                    cmd.append(name)  # store_true flag
                # else don't append
            else:
                if val.strip():
                    cmd.extend([name, val.strip()])

        # Extra args
        extra = self.extra_args_input.text().strip()
        if extra:
            import shlex
            cmd.extend(shlex.split(extra))

        return cmd

    def _on_run(self):
        if not self._script_path:
            return

        # Kill previous process if running
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()

        cmd = self._build_command()
        self._append_output(f"\n[Run] {' '.join(cmd)}\n{'─' * 40}\n")

        self._process = QProcess(self)
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_process_finished)

        # Use venv python if running inside one
        env = QProcessEnvironment.systemEnvironment()
        self._process.setProcessEnvironment(env)
        self._process.setProgram(cmd[0])
        self._process.setArguments(cmd[1:])
        self._process.start()

        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def _on_stop(self):
        if self._process:
            self._process.kill()
            self._append_output("\n[Stopped by user]\n")

    def _on_stdout(self):
        if self._process:
            data = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
            self._append_output(data)

    def _on_stderr(self):
        if self._process:
            data = bytes(self._process.readAllStandardError()).decode("utf-8", errors="replace")
            self._append_output(data, error=True)

    def _on_process_finished(self, exit_code: int, exit_status):
        self._append_output(f"\n{'─' * 40}\n[Finished] Exit code: {exit_code}\n")
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def _on_clear(self):
        self.output_box.clear()

    def _on_favorite(self):
        if not self._script_path:
            return
        from PyQt6.QtWidgets import QInputDialog
        filename = os.path.basename(self._script_path)
        default_name = os.path.splitext(filename)[0].replace("_", " ").title()
        name, ok = QInputDialog.getText(
            self,
            "Add to Favorites",
            "Enter a name for this script:",
            text=default_name,
        )
        if ok and name.strip():
            # Gather current args as saved snapshot
            saved_args = []
            for i, arg in enumerate(self._args_data):
                combo = self.args_table.cellWidget(i, 2)
                if combo:
                    saved_args.append(combo.currentText())
                else:
                    item = self.args_table.item(i, 2)
                    saved_args.append(item.text() if item else "")
            self.add_to_favorites.emit(self._script_path, name.strip(), saved_args, self._script_content)

    # ── Output ────────────────────────────────────────────────────────────────

    def _append_output(self, text: str, error: bool = False):
        cursor = self.output_box.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.output_box.setTextCursor(cursor)

        if error:
            self.output_box.setStyleSheet(self.output_box.styleSheet())
            # Insert red-coloured text via HTML
            escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
            self.output_box.insertHtml(f"<span style='color:#ff8080'>{escaped}</span>")
        else:
            self.output_box.insertPlainText(text)

        # Auto-scroll
        bar = self.output_box.verticalScrollBar()
        bar.setValue(bar.maximum())
