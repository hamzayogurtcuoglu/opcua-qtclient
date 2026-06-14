"""Theme stylesheet and color constants for the OPC UA Client."""

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

DARK_PALETTE = {
    # Backgrounds
    "BG_DARKEST": "#0b0f19",    # Very deep navy/grey
    "BG_DARK": "#111827",       # Gray-900
    "BG_MEDIUM": "#1f2937",     # Gray-800
    "BG_CARD": "#1f2937",       # Gray-800
    "BG_SURFACE": "#374151",    # Gray-700
    "BG_HOVER": "#374151",      # Gray-700
    "BG_INPUT": "#111827",      # Gray-900
    # Borders
    "BORDER": "#374151",        # Gray-700
    "BORDER_LIGHT": "#4b5563",  # Gray-600
    "BORDER_FOCUS": "#6366f1",  # Indigo-500
    # Text
    "TEXT_PRIMARY": "#f9fafb",  # Gray-50
    "TEXT_SECONDARY": "#9ca3af",# Gray-400
    "TEXT_MUTED": "#6b7280",    # Gray-500
    "TEXT_BRIGHT": "#ffffff",   # Pure white
    # Accent / Primary
    "ACCENT": "#6366f1",        # Indigo-500
    "ACCENT_HOVER": "#818cf8",  # Indigo-400
    "ACCENT_DARK": "#4f46e5",   # Indigo-600
    # Status colors
    "SUCCESS": "#10b981",       # Emerald-500
    "SUCCESS_BG": "#064e3b",    # Emerald-900
    "WARNING": "#f59e0b",       # Amber-500
    "WARNING_BG": "#78350f",    # Amber-900
    "ERROR": "#ef4444",         # Red-500
    "ERROR_BG": "#7f1d1d",      # Red-900
    # Node type colors
    "NODE_OBJECT": "#f59e0b",
    "NODE_VARIABLE": "#3b82f6",
    "NODE_METHOD": "#a855f7",
    "NODE_VIEW": "#06b6d4",
    # Badges
    "BADGE_VARIABLE": "#1e3a8a",
    "BADGE_VARIABLE_TEXT": "#bfdbfe",
    "BADGE_METHOD": "#581c87",
    "BADGE_METHOD_TEXT": "#e9d5ff",
    # Scrollbar
    "SCROLLBAR_BG": "transparent",
    "SCROLLBAR_HANDLE": "#4b5563",
    "SCROLLBAR_HOVER": "#6b7280",
}

LIGHT_PALETTE = {
    # Backgrounds
    "BG_DARKEST": "#f3f4f6",    # Gray-100
    "BG_DARK": "#f9fafb",       # Gray-50
    "BG_MEDIUM": "#e5e7eb",     # Gray-200
    "BG_CARD": "#ffffff",       # White
    "BG_SURFACE": "#f3f4f6",    # Gray-100
    "BG_HOVER": "#e5e7eb",      # Gray-200
    "BG_INPUT": "#ffffff",      # White
    # Borders
    "BORDER": "#e5e7eb",        # Gray-200
    "BORDER_LIGHT": "#d1d5db",  # Gray-300
    "BORDER_FOCUS": "#6366f1",  # Indigo-500
    # Text
    "TEXT_PRIMARY": "#111827",  # Gray-900
    "TEXT_SECONDARY": "#4b5563",# Gray-600
    "TEXT_MUTED": "#9ca3af",    # Gray-400
    "TEXT_BRIGHT": "#000000",   # Pure black
    # Accent / Primary
    "ACCENT": "#4f46e5",        # Indigo-600
    "ACCENT_HOVER": "#6366f1",  # Indigo-500
    "ACCENT_DARK": "#4338ca",   # Indigo-700
    # Status colors
    "SUCCESS": "#059669",       # Emerald-600
    "SUCCESS_BG": "#d1fae5",    # Emerald-100
    "WARNING": "#d97706",       # Amber-600
    "WARNING_BG": "#fef3c7",    # Amber-100
    "ERROR": "#dc2626",         # Red-600
    "ERROR_BG": "#fee2e2",      # Red-100
    # Node type colors
    "NODE_OBJECT": "#d97706",
    "NODE_VARIABLE": "#2563eb",
    "NODE_METHOD": "#9333ea",
    "NODE_VIEW": "#0891b2",
    # Badges
    "BADGE_VARIABLE": "#dbeafe",
    "BADGE_VARIABLE_TEXT": "#1e40af",
    "BADGE_METHOD": "#f3e8ff",
    "BADGE_METHOD_TEXT": "#6b21a8",
    # Scrollbar
    "SCROLLBAR_BG": "transparent",
    "SCROLLBAR_HANDLE": "#d1d5db",
    "SCROLLBAR_HOVER": "#9ca3af",
}

SYSTEM_PALETTE = {
    # Backgrounds
    "BG_DARKEST": "#d4d4d4",    # Classic gray
    "BG_DARK": "#e5e5e5",       # Lighter gray
    "BG_MEDIUM": "#f5f5f5",     # Almost white
    "BG_CARD": "#f0f0f0",       # Card background
    "BG_SURFACE": "#e5e5e5",    
    "BG_HOVER": "#d4d4d4",      
    "BG_INPUT": "#ffffff",      
    # Borders
    "BORDER": "#a3a3a3",        
    "BORDER_LIGHT": "#d4d4d4",  
    "BORDER_FOCUS": "#3b82f6",  
    # Text
    "TEXT_PRIMARY": "#171717",  
    "TEXT_SECONDARY": "#525252",
    "TEXT_MUTED": "#737373",    
    "TEXT_BRIGHT": "#000000",   
    # Accent / Primary
    "ACCENT": "#3b82f6",        
    "ACCENT_HOVER": "#60a5fa",  
    "ACCENT_DARK": "#2563eb",   
    # Status colors
    "SUCCESS": "#16a34a",       
    "SUCCESS_BG": "#dcfce7",    
    "WARNING": "#d97706",       
    "WARNING_BG": "#fef3c7",    
    "ERROR": "#dc2626",         
    "ERROR_BG": "#fee2e2",      
    # Node type colors
    "NODE_OBJECT": "#d97706",
    "NODE_VARIABLE": "#2563eb",
    "NODE_METHOD": "#9333ea",
    "NODE_VIEW": "#0891b2",
    # Badges
    "BADGE_VARIABLE": "#dbeafe",
    "BADGE_VARIABLE_TEXT": "#1e40af",
    "BADGE_METHOD": "#f3e8ff",
    "BADGE_METHOD_TEXT": "#6b21a8",
    # Scrollbar
    "SCROLLBAR_BG": "transparent",
    "SCROLLBAR_HANDLE": "#a3a3a3",
    "SCROLLBAR_HOVER": "#737373",
}


class Colors:
    """Centralized color palette."""
    BG_DARKEST = DARK_PALETTE["BG_DARKEST"]
    BG_DARK = DARK_PALETTE["BG_DARK"]
    BG_MEDIUM = DARK_PALETTE["BG_MEDIUM"]
    BG_CARD = DARK_PALETTE["BG_CARD"]
    BG_SURFACE = DARK_PALETTE["BG_SURFACE"]
    BG_HOVER = DARK_PALETTE["BG_HOVER"]
    BG_INPUT = DARK_PALETTE["BG_INPUT"]

    BORDER = DARK_PALETTE["BORDER"]
    BORDER_LIGHT = DARK_PALETTE["BORDER_LIGHT"]
    BORDER_FOCUS = DARK_PALETTE["BORDER_FOCUS"]

    TEXT_PRIMARY = DARK_PALETTE["TEXT_PRIMARY"]
    TEXT_SECONDARY = DARK_PALETTE["TEXT_SECONDARY"]
    TEXT_MUTED = DARK_PALETTE["TEXT_MUTED"]
    TEXT_BRIGHT = DARK_PALETTE["TEXT_BRIGHT"]

    ACCENT = DARK_PALETTE["ACCENT"]
    ACCENT_HOVER = DARK_PALETTE["ACCENT_HOVER"]
    ACCENT_DARK = DARK_PALETTE["ACCENT_DARK"]

    SUCCESS = DARK_PALETTE["SUCCESS"]
    SUCCESS_BG = DARK_PALETTE["SUCCESS_BG"]
    WARNING = DARK_PALETTE["WARNING"]
    WARNING_BG = DARK_PALETTE["WARNING_BG"]
    ERROR = DARK_PALETTE["ERROR"]
    ERROR_BG = DARK_PALETTE["ERROR_BG"]

    NODE_OBJECT = DARK_PALETTE["NODE_OBJECT"]
    NODE_VARIABLE = DARK_PALETTE["NODE_VARIABLE"]
    NODE_METHOD = DARK_PALETTE["NODE_METHOD"]
    NODE_VIEW = DARK_PALETTE["NODE_VIEW"]

    BADGE_VARIABLE = DARK_PALETTE["BADGE_VARIABLE"]
    BADGE_VARIABLE_TEXT = DARK_PALETTE["BADGE_VARIABLE_TEXT"]
    BADGE_METHOD = DARK_PALETTE["BADGE_METHOD"]
    BADGE_METHOD_TEXT = DARK_PALETTE["BADGE_METHOD_TEXT"]

    SCROLLBAR_BG = DARK_PALETTE["SCROLLBAR_BG"]
    SCROLLBAR_HANDLE = DARK_PALETTE["SCROLLBAR_HANDLE"]
    SCROLLBAR_HOVER = DARK_PALETTE["SCROLLBAR_HOVER"]


class ThemeManager(QObject):
    theme_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.current_mode = "dark"

    def apply_theme(self, mode: str):
        self.current_mode = mode
        if mode == "light":
            palette = LIGHT_PALETTE
        elif mode == "system":
            palette = SYSTEM_PALETTE
        else:
            palette = DARK_PALETTE

        # Update Colors class variables
        for key, value in palette.items():
            setattr(Colors, key, value)

        # Update global app stylesheet
        app = QApplication.instance()
        if app:
            app.setStyleSheet(get_stylesheet())

        # Notify widgets to update their inline styles
        self.theme_changed.emit()

theme_manager = ThemeManager()


def get_stylesheet() -> str:
    """Return the complete application stylesheet."""
    return f"""
    /* ===== Global ===== */
    * {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Inter", "Helvetica Neue", Arial, sans-serif;
        font-size: 14px;
    }}

    QMainWindow {{
        background-color: {Colors.BG_DARKEST};
    }}

    QWidget {{
        background-color: {Colors.BG_DARKEST};
        color: {Colors.TEXT_PRIMARY};
    }}

    /* ===== Tool Bar ===== */
    QToolBar {{
        background-color: {Colors.BG_DARK};
        border-bottom: 1px solid {Colors.BORDER};
        padding: 4px 8px;
        spacing: 6px;
    }}

    QToolBar QToolButton {{
        background-color: transparent;
        color: {Colors.TEXT_SECONDARY};
        border: none;
        border-radius: 6px;
        padding: 6px 12px;
        font-size: 12px;
    }}

    QToolBar QToolButton:hover {{
        background-color: {Colors.BG_HOVER};
        color: {Colors.TEXT_PRIMARY};
    }}

    QToolBar QToolButton:pressed {{
        background-color: {Colors.BG_SURFACE};
    }}

    /* ===== Frames / Group Boxes ===== */
    QFrame[frameShape="6"] {{ /* StyledPanel */
        background-color: {Colors.BG_CARD};
        border: none;
        border-radius: 12px;
    }}

    QGroupBox {{
        background-color: {Colors.BG_CARD};
        border: 1px solid {Colors.BORDER};
        border-radius: 12px;
        margin-top: 18px;
        padding: 16px 12px 12px 12px;
        font-weight: 600;
        font-size: 14px;
        color: {Colors.TEXT_PRIMARY};
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 2px 10px;
        color: {Colors.TEXT_PRIMARY};
    }}

    /* ===== Labels ===== */
    QLabel {{
        background-color: transparent;
        color: {Colors.TEXT_PRIMARY};
        border: none;
    }}

    QLabel[class="header"] {{
        font-size: 15px;
        font-weight: bold;
    }}

    QLabel[class="subtitle"] {{
        font-size: 11px;
        color: {Colors.TEXT_SECONDARY};
    }}

    QLabel[class="muted"] {{
        color: {Colors.TEXT_MUTED};
    }}

    /* ===== Line Edits / Search ===== */
    QLineEdit {{
        background-color: {Colors.BG_INPUT};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        padding: 8px 12px;
        font-size: 13px;
        selection-background-color: {Colors.ACCENT};
    }}

    QLineEdit:focus {{
        border: 1px solid {Colors.BORDER_FOCUS};
    }}

    QLineEdit::placeholder {{
        color: {Colors.TEXT_MUTED};
    }}

    /* ===== Buttons ===== */
    QPushButton {{
        background-color: {Colors.BG_SURFACE};
        color: {Colors.TEXT_PRIMARY};
        border: none;
        border-radius: 8px;
        padding: 8px 16px;
        font-size: 13px;
        font-weight: 600;
    }}

    QPushButton:hover {{
        background-color: {Colors.BG_HOVER};
        border-color: {Colors.BORDER_LIGHT};
    }}

    QPushButton:pressed {{
        background-color: {Colors.BG_CARD};
    }}

    QPushButton:disabled {{
        background-color: {Colors.BG_MEDIUM};
        color: {Colors.TEXT_MUTED};
        border-color: {Colors.BORDER};
    }}

    QPushButton[class="primary"] {{
        background-color: {Colors.ACCENT};
        color: white;
        border: none;
        font-weight: 600;
    }}

    QPushButton[class="primary"]:hover {{
        background-color: {Colors.ACCENT_HOVER};
    }}

    QPushButton[class="primary"]:pressed {{
        background-color: {Colors.ACCENT_DARK};
    }}

    QPushButton[class="danger"] {{
        background-color: {Colors.ERROR};
        color: white;
        border: none;
    }}

    QPushButton[class="danger"]:hover {{
        background-color: #dc2626;
    }}

    QPushButton[class="flat"] {{
        background-color: transparent;
        border: none;
        color: {Colors.TEXT_SECONDARY};
    }}

    QPushButton[class="flat"]:hover {{
        color: {Colors.TEXT_PRIMARY};
        background-color: {Colors.BG_HOVER};
    }}

    /* ===== Tab Widget ===== */
    QTabWidget::pane {{
        border: 1px solid {Colors.BORDER};
        border-radius: 0px;
        background-color: {Colors.BG_DARK};
        top: -1px;
    }}

    QTabBar {{
        background-color: transparent;
    }}

    QTabBar::tab {{
        background-color: transparent;
        color: {Colors.TEXT_SECONDARY};
        border: none;
        border-bottom: 2px solid transparent;
        padding: 10px 16px;
        margin-right: 4px;
        font-size: 13px;
        font-weight: 500;
    }}

    QTabBar::tab:selected {{
        color: {Colors.ACCENT};
        border-bottom: 2px solid {Colors.ACCENT};
    }}

    QTabBar::tab:hover:!selected {{
        color: {Colors.TEXT_PRIMARY};
        background-color: {Colors.BG_HOVER};
    }}

    QTabBar::close-button {{
        image: none;
        subcontrol-position: right;
        padding: 2px;
    }}

    /* ===== Tree Widget ===== */
    QTreeWidget, QTreeView {{
        background-color: transparent;
        color: {Colors.TEXT_PRIMARY};
        border: none;
        outline: none;
        padding: 4px;
        font-size: 13px;
    }}

    QTreeWidget::item, QTreeView::item {{
        padding: 4px 6px;
        border-radius: 4px;
        margin: 1px 0px;
        color: {Colors.TEXT_PRIMARY};
    }}

    QTreeWidget::item:selected, QTreeView::item:selected {{
        background-color: {Colors.ACCENT};
        color: white;
    }}

    QTreeWidget::item:hover:!selected, QTreeView::item:hover:!selected {{
        background-color: {Colors.BG_HOVER};
    }}

    QTreeWidget::branch {{
        background-color: transparent;
    }}

    QHeaderView::section {{
        background-color: {Colors.BG_MEDIUM};
        color: {Colors.TEXT_SECONDARY};
        border: none;
        border-bottom: 1px solid {Colors.BORDER};
        border-right: 1px solid {Colors.BORDER};
        padding: 6px 10px;
        font-size: 11px;
        font-weight: bold;
    }}

    /* ===== Table Widget ===== */
    QTableWidget, QTableView {{
        background-color: transparent;
        color: {Colors.TEXT_PRIMARY};
        border: none;
        gridline-color: {Colors.BORDER};
        outline: none;
        font-size: 13px;
    }}

    QTableWidget::item, QTableView::item {{
        padding: 4px 8px;
        border-bottom: 1px solid {Colors.BORDER};
        color: {Colors.TEXT_PRIMARY};
    }}

    QTableWidget::item:selected, QTableView::item:selected {{
        background-color: {Colors.ACCENT};
        color: white;
    }}

    /* ===== Scroll Bars ===== */
    QScrollBar:vertical {{
        background-color: {Colors.SCROLLBAR_BG};
        width: 10px;
        margin: 0px;
        border-radius: 5px;
    }}

    QScrollBar::handle:vertical {{
        background-color: {Colors.SCROLLBAR_HANDLE};
        min-height: 30px;
        border-radius: 5px;
    }}

    QScrollBar::handle:vertical:hover {{
        background-color: {Colors.SCROLLBAR_HOVER};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: none;
    }}

    QScrollBar:horizontal {{
        background-color: {Colors.SCROLLBAR_BG};
        height: 10px;
        margin: 0px;
        border-radius: 5px;
    }}

    QScrollBar::handle:horizontal {{
        background-color: {Colors.SCROLLBAR_HANDLE};
        min-width: 30px;
        border-radius: 5px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background-color: {Colors.SCROLLBAR_HOVER};
    }}

    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}

    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: none;
    }}

    /* ===== Splitter ===== */
    QSplitter::handle {{
        background-color: {Colors.BORDER};
        width: 1px;
        height: 1px;
    }}

    QSplitter::handle:hover {{
        background-color: {Colors.ACCENT};
    }}

    /* ===== Combo Box ===== */
    QComboBox {{
        background-color: {Colors.BG_INPUT};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        padding: 8px 12px;
        font-size: 13px;
        min-width: 100px;
    }}

    QComboBox:focus {{
        border-color: {Colors.BORDER_FOCUS};
    }}

    QComboBox::drop-down {{
        border: none;
        padding-right: 8px;
    }}

    QComboBox::down-arrow {{
        image: none;
        border: none;
        width: 0;
        height: 0;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {Colors.TEXT_SECONDARY};
    }}

    QComboBox QAbstractItemView {{
        background-color: {Colors.BG_CARD};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER};
        border-radius: 6px;
        selection-background-color: {Colors.ACCENT};
        padding: 4px;
    }}

    /* ===== Spin Box ===== */
    QSpinBox, QDoubleSpinBox {{
        background-color: {Colors.BG_INPUT};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        padding: 6px 10px;
    }}

    QSpinBox:focus, QDoubleSpinBox:focus {{
        border-color: {Colors.BORDER_FOCUS};
    }}

    /* ===== Check Box ===== */
    QCheckBox {{
        color: {Colors.TEXT_PRIMARY};
        spacing: 8px;
        background: transparent;
    }}

    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 2px solid {Colors.BORDER_LIGHT};
        border-radius: 4px;
        background-color: {Colors.BG_INPUT};
    }}

    QCheckBox::indicator:checked {{
        background-color: {Colors.ACCENT};
        border-color: {Colors.ACCENT};
    }}

    /* ===== Menu ===== */
    QMenu {{
        background-color: {Colors.BG_CARD};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        padding: 4px;
    }}

    QMenu::item {{
        padding: 6px 24px;
        border-radius: 4px;
    }}

    QMenu::item:selected {{
        background-color: {Colors.ACCENT};
        color: white;
    }}

    QMenu::separator {{
        height: 1px;
        background-color: {Colors.BORDER};
        margin: 4px 8px;
    }}

    /* ===== Dialog ===== */
    QDialog {{
        background-color: {Colors.BG_DARK};
        border: 1px solid {Colors.BORDER};
        border-radius: 12px;
    }}

    /* ===== Tooltip ===== */
    QToolTip {{
        background-color: {Colors.BG_CARD};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER};
        border-radius: 6px;
        padding: 4px 8px;
        font-size: 11px;
    }}

    /* ===== Status Bar ===== */
    QStatusBar {{
        background-color: {Colors.BG_DARK};
        color: {Colors.TEXT_SECONDARY};
        border-top: 1px solid {Colors.BORDER};
        font-size: 11px;
    }}
    """
