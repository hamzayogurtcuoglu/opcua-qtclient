"""Dialog for manually adding an OPC UA server."""

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QPushButton, QFormLayout, QFrame,
)

from app.models import ServerInfo
from app.theme import Colors


class AddServerDialog(QDialog):
    """Dialog for adding a new OPC UA server manually."""

    def __init__(self, parent: Optional[object] = None, edit_server: Optional[ServerInfo] = None):
        super().__init__(parent)
        self._edit_server = edit_server
        self._result: Optional[ServerInfo] = None
        self._setup_ui()
        if edit_server:
            self._populate(edit_server)

    def _setup_ui(self):
        self.setWindowTitle("Add Server" if not self._edit_server else "Edit Server")
        self.setMinimumWidth(450)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Colors.BG_DARK};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Title
        title = QLabel("Add OPC UA Server" if not self._edit_server else "Edit OPC UA Server")
        title.setStyleSheet(f"""
            font-size: 18px;
            font-weight: bold;
            color: {Colors.TEXT_PRIMARY};
            background: transparent;
        """)
        layout.addWidget(title)

        subtitle = QLabel("Enter the server connection details below.")
        subtitle.setStyleSheet(f"""
            font-size: 12px;
            color: {Colors.TEXT_SECONDARY};
            background: transparent;
        """)
        layout.addWidget(subtitle)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {Colors.BORDER}; max-height: 1px;")
        layout.addWidget(sep)

        # Form
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Local Simulation Server")
        form.addRow("Server Name:", self.name_input)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("opc.tcp://localhost:4840")
        self.url_input.setText("opc.tcp://")
        form.addRow("Server URL:", self.url_input)

        self.security_combo = QComboBox()
        self.security_combo.addItems([
            "None",
            "Basic128Rsa15",
            "Basic256",
            "Basic256Sha256",
            "Aes128Sha256RsaOaep",
            "Aes256Sha256RsaPss",
        ])
        form.addRow("Security Policy:", self.security_combo)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("(optional)")
        form.addRow("Username:", self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("(optional)")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Password:", self.password_input)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumWidth(100)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save" if self._edit_server else "Add Server")
        save_btn.setProperty("class", "primary")
        save_btn.setMinimumWidth(120)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _populate(self, server: ServerInfo):
        self.name_input.setText(server.name)
        self.url_input.setText(server.url)
        idx = self.security_combo.findText(server.security_policy)
        if idx >= 0:
            self.security_combo.setCurrentIndex(idx)
        self.username_input.setText(server.username)
        self.password_input.setText(server.password)

    def _on_save(self):
        name = self.name_input.text().strip()
        url = self.url_input.text().strip()

        if not name:
            self.name_input.setFocus()
            self.name_input.setStyleSheet(f"border: 1px solid {Colors.ERROR};")
            return

        if not url or url == "opc.tcp://":
            self.url_input.setFocus()
            self.url_input.setStyleSheet(f"border: 1px solid {Colors.ERROR};")
            return

        self._result = ServerInfo(
            name=name,
            url=url,
            security_policy=self.security_combo.currentText(),
            username=self.username_input.text().strip(),
            password=self.password_input.text(),
        )
        self.accept()

    def get_result(self) -> Optional[ServerInfo]:
        return self._result
