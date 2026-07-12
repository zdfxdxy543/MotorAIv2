"""
QSS stylesheet for the HardwareConfig standalone application.
"""

# Colour tokens
COLOR_BG = "#f5f6fa"
COLOR_SURFACE = "#ffffff"
COLOR_PRIMARY = "#0f62fe"
COLOR_PRIMARY_HOVER = "#0353e9"
COLOR_TEXT = "#1a1a2e"
COLOR_TEXT_SECONDARY = "#6b7280"
COLOR_TEXT_MUTED = "#9ca3af"
COLOR_BORDER = "#e2e4e9"
COLOR_ACCENT_BG = "#eef2ff"
COLOR_SELECTED_BG = "#dbeafe"
COLOR_INPUT_BG = "#f9fafb"
COLOR_INPUT_BORDER = "#d1d5db"
COLOR_INPUT_FOCUS = "#0f62fe"
COLOR_LOCKED_BG = "#f0f0f0"
COLOR_PLACEHOLDER_BG = "#fafafa"
COLOR_DANGER = "#ef4444"

FONT_FAMILY = '"Microsoft YaHei", "Segoe UI", "PingFang SC", sans-serif'
FONT_SIZE_BASE = "13px"
FONT_SIZE_SMALL = "12px"
FONT_SIZE_TITLE = "15px"
FONT_SIZE_HEADING = "14px"

RADIUS_CARD = 8
RADIUS_CONTROL = 6
RADIUS_SMALL = 4


def app_stylesheet() -> str:
    return f"""
    /* ===== Global ===== */
    QMainWindow {{
        background-color: {COLOR_BG};
    }}
    QWidget {{
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE_BASE};
        color: {COLOR_TEXT};
    }}

    /* ===== Scrollbar ===== */
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: #c4c8d0;
        border-radius: 4px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: #a0a5b0;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}

    /* ===== Search box ===== */
    QLineEdit#searchBox {{
        background: {COLOR_INPUT_BG};
        border: 1px solid {COLOR_INPUT_BORDER};
        border-radius: {RADIUS_CONTROL}px;
        padding: 8px 12px;
        font-size: {FONT_SIZE_BASE};
        color: {COLOR_TEXT};
    }}
    QLineEdit#searchBox:focus {{
        border-color: {COLOR_INPUT_FOCUS};
        background: {COLOR_SURFACE};
    }}

    /* ===== Preset list ===== */
    QListWidget#presetList {{
        background: {COLOR_SURFACE};
        border: 1px solid {COLOR_BORDER};
        border-radius: {RADIUS_CARD}px;
        padding: 4px;
        outline: none;
    }}
    QListWidget#presetList::item {{
        padding: 10px 12px;
        border-radius: {RADIUS_SMALL}px;
        margin: 1px 0;
    }}
    QListWidget#presetList::item:hover {{
        background: {COLOR_ACCENT_BG};
    }}
    QListWidget#presetList::item:selected {{
        background: {COLOR_SELECTED_BG};
        color: {COLOR_TEXT};
    }}

    /* ===== Section cards ===== */
    QFrame#sectionCard {{
        background: {COLOR_SURFACE};
        border: 1px solid {COLOR_BORDER};
        border-radius: {RADIUS_CARD}px;
        padding: 0;
    }}

    /* ===== Section header ===== */
    QLabel#sectionHeader {{
        font-size: {FONT_SIZE_HEADING};
        font-weight: 600;
        color: {COLOR_TEXT};
        padding: 4px 0;
    }}

    /* ===== Param row labels ===== */
    QLabel#paramLabel {{
        font-size: {FONT_SIZE_BASE};
        color: {COLOR_TEXT};
    }}
    QLabel#paramSymbol {{
        font-size: {FONT_SIZE_SMALL};
        color: {COLOR_TEXT_SECONDARY};
    }}
    QLabel#paramUnit {{
        font-size: {FONT_SIZE_SMALL};
        color: {COLOR_TEXT_MUTED};
    }}
    QLabel#fluxHint {{
        font-size: {FONT_SIZE_SMALL};
        color: {COLOR_TEXT_MUTED};
        font-style: italic;
    }}
    QLabel#emptyPlaceholder {{
        font-size: {FONT_SIZE_SMALL};
        color: {COLOR_TEXT_MUTED};
        font-style: italic;
    }}

    /* ===== Spinbox ===== */
    QDoubleSpinBox {{
        background: {COLOR_INPUT_BG};
        border: 1px solid {COLOR_INPUT_BORDER};
        border-radius: {RADIUS_CONTROL}px;
        padding: 6px 10px;
        font-size: {FONT_SIZE_BASE};
        font-family: "Consolas", "Cascadia Code", monospace;
        color: {COLOR_TEXT};
        min-height: 20px;
    }}
    QDoubleSpinBox:focus {{
        border-color: {COLOR_INPUT_FOCUS};
        background: {COLOR_SURFACE};
    }}
    QDoubleSpinBox:disabled {{
        background: {COLOR_LOCKED_BG};
        color: {COLOR_TEXT_SECONDARY};
    }}

    /* ===== Tab buttons ===== */
    QPushButton#tabButton {{
        background: transparent;
        color: {COLOR_TEXT_SECONDARY};
        border: none;
        border-bottom: 2px solid transparent;
        border-radius: 0;
        padding: 8px 20px;
        font-size: {FONT_SIZE_BASE};
        font-weight: 500;
    }}
    QPushButton#tabButton:hover {{
        color: {COLOR_TEXT};
        background: {COLOR_ACCENT_BG};
    }}
    QPushButton#tabButton:checked {{
        color: {COLOR_PRIMARY};
        border-bottom: 2px solid {COLOR_PRIMARY};
        font-weight: 600;
    }}

    /* ===== Table ===== */
    QTableWidget {{
        background: {COLOR_SURFACE};
        border: 1px solid {COLOR_BORDER};
        border-radius: {RADIUS_SMALL}px;
        gridline-color: #e8eaed;
        outline: none;
        alternate-background-color: #f8f9fb;
    }}
    QTableWidget::item {{
        padding: 5px 10px;
    }}
    QHeaderView::section {{
        background: #f0f1f4;
        color: {COLOR_TEXT};
        font-size: {FONT_SIZE_BASE};
        font-weight: 600;
        border: none;
        border-right: 1px solid #e2e4e9;
        border-bottom: 1px solid {COLOR_BORDER};
        padding: 7px 10px;
    }}

    /* ===== Buttons ===== */
    QPushButton#primaryButton {{
        background: {COLOR_PRIMARY};
        color: white;
        border: none;
        border-radius: {RADIUS_CONTROL}px;
        padding: 10px 24px;
        font-size: {FONT_SIZE_BASE};
        font-weight: 600;
    }}
    QPushButton#primaryButton:hover {{
        background: {COLOR_PRIMARY_HOVER};
    }}
    QPushButton#primaryButton:disabled {{
        background: #a0c4ff;
    }}

    QPushButton#secondaryButton {{
        background: transparent;
        color: {COLOR_TEXT};
        border: 1px solid {COLOR_BORDER};
        border-radius: {RADIUS_CONTROL}px;
        padding: 8px 18px;
        font-size: {FONT_SIZE_BASE};
    }}
    QPushButton#secondaryButton:hover {{
        background: {COLOR_ACCENT_BG};
        border-color: {COLOR_PRIMARY};
        color: {COLOR_PRIMARY};
    }}

    QPushButton#lockButton {{
        background: transparent;
        border: none;
        font-size: 16px;
        padding: 4px;
        min-width: 28px;
        min-height: 28px;
    }}
    QPushButton#lockButton:hover {{
        background: {COLOR_BORDER};
        border-radius: {RADIUS_SMALL}px;
    }}

    /* ===== Status bar ===== */
    QStatusBar {{
        background: {COLOR_SURFACE};
        border-top: 1px solid {COLOR_BORDER};
        padding: 4px 12px;
        font-size: {FONT_SIZE_SMALL};
        color: {COLOR_TEXT_SECONDARY};
    }}

    /* ===== Menu bar ===== */
    QMenuBar {{
        background: {COLOR_SURFACE};
        border-bottom: 1px solid {COLOR_BORDER};
        padding: 2px 0;
    }}
    QMenuBar::item {{
        padding: 6px 12px;
    }}
    QMenuBar::item:selected {{
        background: {COLOR_ACCENT_BG};
    }}
    QMenu {{
        background: {COLOR_SURFACE};
        border: 1px solid {COLOR_BORDER};
        border-radius: {RADIUS_SMALL}px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: 8px 32px 8px 16px;
    }}
    QMenu::item:selected {{
        background: {COLOR_ACCENT_BG};
    }}

    /* ===== Group box ===== */
    QGroupBox {{
        font-weight: 600;
        border: 1px solid {COLOR_BORDER};
        border-radius: {RADIUS_CARD}px;
        margin-top: 16px;
        padding-top: 20px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
    }}

    /* ===== Splitter ===== */
    QSplitter::handle {{
        background: {COLOR_BORDER};
        margin: 0 2px;
    }}
    QSplitter::handle:horizontal {{
        width: 1px;
    }}

    /* ===== Toolbar ===== */
    QToolBar {{
        background: {COLOR_SURFACE};
        border-bottom: 1px solid {COLOR_BORDER};
        spacing: 8px;
        padding: 4px 8px;
    }}
    """
