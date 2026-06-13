"""Dark theme stylesheet and color constants for the OPC UA Client."""


class Colors:
    """Centralized color palette."""
    # Backgrounds
    BG_DARKEST = "#0f1117"
    BG_DARK = "#161b22"
    BG_MEDIUM = "#1c2333"
    BG_CARD = "#1e293b"
    BG_SURFACE = "#243044"
    BG_HOVER = "#2a3a52"
    BG_INPUT = "#131a27"

    # Borders
    BORDER = "#2d3748"
    BORDER_LIGHT = "#3a4a5e"
    BORDER_FOCUS = "#4f8cff"

    # Text
    TEXT_PRIMARY = "#e2e8f0"
    TEXT_SECONDARY = "#94a3b8"
    TEXT_MUTED = "#64748b"
    TEXT_BRIGHT = "#f8fafc"

    # Accent / Primary
    ACCENT = "#4f8cff"
    ACCENT_HOVER = "#6ba1ff"
    ACCENT_DARK = "#3b6fd4"

    # Status colors
    SUCCESS = "#22c55e"
    SUCCESS_BG = "#15392b"
    WARNING = "#f59e0b"
    WARNING_BG = "#3d2f0a"
    ERROR = "#ef4444"
    ERROR_BG = "#3d1515"

    # Node type colors
    NODE_OBJECT = "#f59e0b"    # Yellow/amber for folders/objects
    NODE_VARIABLE = "#4f8cff"  # Blue for variables
    NODE_METHOD = "#a855f7"    # Purple for methods
    NODE_VIEW = "#06b6d4"      # Cyan for views

    # Badges
    BADGE_VARIABLE = "#1e40af"
    BADGE_VARIABLE_TEXT = "#93c5fd"
    BADGE_METHOD = "#6b21a8"
    BADGE_METHOD_TEXT = "#c4b5fd"

    # Scrollbar
    SCROLLBAR_BG = "#1c2333"
    SCROLLBAR_HANDLE = "#3a4a5e"
    SCROLLBAR_HOVER = "#4a5a6e"


def get_stylesheet() -> str:
    """Return the complete application stylesheet."""
    return f"""
    /* ===== Global ===== */
    * {{
        font-family: 'Helvetica Neue', 'Helvetica', 'Arial';
        font-size: 13px;
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
        background-color: {Colors.BG_DARK};
        border: 1px solid {Colors.BORDER};
        border-radius: 10px;
    }}

    QGroupBox {{
        background-color: {Colors.BG_DARK};
        border: 1px solid {Colors.BORDER};
        border-radius: 10px;
        margin-top: 16px;
        padding: 16px 10px 10px 10px;
        font-weight: bold;
        font-size: 13px;
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
        padding: 7px 12px;
        font-size: 12px;
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
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        padding: 7px 16px;
        font-size: 12px;
        font-weight: 500;
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
        font-weight: bold;
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
        padding: 8px 16px;
        margin-right: 2px;
        font-size: 12px;
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
        background-color: {Colors.BG_DARK};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        outline: none;
        padding: 4px;
        font-size: 12px;
    }}

    QTreeWidget::item, QTreeView::item {{
        padding: 4px 6px;
        border-radius: 4px;
        margin: 1px 0px;
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
        background-color: {Colors.BG_DARK};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        gridline-color: {Colors.BORDER};
        outline: none;
        font-size: 12px;
    }}

    QTableWidget::item, QTableView::item {{
        padding: 4px 8px;
        border-bottom: 1px solid {Colors.BORDER};
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
        padding: 6px 12px;
        font-size: 12px;
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
        border-radius: 6px;
        padding: 4px 8px;
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
