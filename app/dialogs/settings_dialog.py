"""Settings dialog for application configuration."""

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSpinBox, QCheckBox, QComboBox,
    QFormLayout, QFrame, QGroupBox,
)

from app.theme import Colors


class SettingsDialog(QDialog):
    """Application settings dialog."""

    def __init__(self, settings: dict = None, parent: Optional[object] = None):
        super().__init__(parent)
        self._settings = settings or {}
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        self.setWindowTitle("Settings")
        self.setMinimumWidth(480)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Colors.BG_DARK};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Title
        title = QLabel("⚙️ Settings")
        title.setStyleSheet(f"""
            font-size: 18px;
            font-weight: bold;
            color: {Colors.TEXT_PRIMARY};
            background: transparent;
        """)
        layout.addWidget(title)

        # Connection settings group
        conn_group = QGroupBox("Connection")
        conn_layout = QFormLayout()
        conn_layout.setSpacing(12)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 120)
        self.timeout_spin.setValue(10)
        self.timeout_spin.setSuffix(" seconds")
        conn_layout.addRow("Connection Timeout:", self.timeout_spin)

        self.auto_reconnect = QCheckBox("Enable automatic reconnection")
        self.auto_reconnect.setChecked(True)
        conn_layout.addRow("", self.auto_reconnect)

        self.reconnect_interval = QSpinBox()
        self.reconnect_interval.setRange(1, 300)
        self.reconnect_interval.setValue(5)
        self.reconnect_interval.setSuffix(" seconds")
        conn_layout.addRow("Reconnect Interval:", self.reconnect_interval)

        self.security_combo = QComboBox()
        self.security_combo.addItems([
            "None",
            "Basic128Rsa15",
            "Basic256",
            "Basic256Sha256",
        ])
        conn_layout.addRow("Default Security:", self.security_combo)

        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)

        # UI settings group
        ui_group = QGroupBox("User Interface")
        ui_layout = QFormLayout()
        ui_layout.setSpacing(12)

        self.max_history_spin = QSpinBox()
        self.max_history_spin.setRange(100, 10000)
        self.max_history_spin.setValue(1000)
        self.max_history_spin.setSingleStep(100)
        ui_layout.addRow("Max History Entries:", self.max_history_spin)

        self.auto_expand = QCheckBox("Auto-expand first level of address space")
        self.auto_expand.setChecked(True)
        ui_layout.addRow("", self.auto_expand)

        self.show_timestamps = QCheckBox("Show timestamps in operation history")
        self.show_timestamps.setChecked(True)
        ui_layout.addRow("", self.show_timestamps)

        ui_group.setLayout(ui_layout)
        layout.addWidget(ui_group)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumWidth(100)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save Settings")
        save_btn.setProperty("class", "primary")
        save_btn.setMinimumWidth(120)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _load_settings(self):
        if self._settings:
            self.timeout_spin.setValue(self._settings.get("timeout", 10))
            self.auto_reconnect.setChecked(self._settings.get("auto_reconnect", True))
            self.reconnect_interval.setValue(self._settings.get("reconnect_interval", 5))
            self.max_history_spin.setValue(self._settings.get("max_history", 1000))
            idx = self.security_combo.findText(self._settings.get("default_security", "None"))
            if idx >= 0:
                self.security_combo.setCurrentIndex(idx)

    def _on_save(self):
        self._settings = {
            "timeout": self.timeout_spin.value(),
            "auto_reconnect": self.auto_reconnect.isChecked(),
            "reconnect_interval": self.reconnect_interval.value(),
            "max_history": self.max_history_spin.value(),
            "default_security": self.security_combo.currentText(),
            "auto_expand": self.auto_expand.isChecked(),
            "show_timestamps": self.show_timestamps.isChecked(),
        }
        self.accept()

    def get_settings(self) -> dict:
        return self._settings
