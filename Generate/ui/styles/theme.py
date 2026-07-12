"""MotorAI UI theming ― light / dark tokens, QSS generators, and painter helpers."""

from __future__ import annotations

from dataclasses import dataclass

from .fonts import FONT_FAMILY_QSS

FONT_FAMILY = FONT_FAMILY_QSS
RADIUS_CARD = 10
RADIUS_CONTROL = 8
RADIUS_BUBBLE = 10
RADIUS_SMALL = 6


# ── Theme dataclass ──────────────────────────────────────────────────
@dataclass(frozen=True)
class Theme:
    name: str

    primary: str
    primary_hover: str
    primary_pressed: str
    primary_soft: str
    primary_border: str
    primary_text: str

    text: str
    text_strong: str
    muted: str
    subtle: str
    border: str
    border_strong: str
    surface: str
    background: str
    panel: str
    panel_hover: str
    selection: str

    success_bg: str
    success_border: str
    success_text: str
    error_bg: str
    error_border: str
    error_text: str

    # Canvas / painter extras
    canvas_bg: str
    canvas_title: str
    canvas_arrow: str
    canvas_placeholder_start: tuple[int, int, int, int]
    canvas_placeholder_end: tuple[int, int, int, int]
    canvas_grid: str
    canvas_grid_bg: str
    canvas_axis: str
    canvas_data_line: str
    canvas_data_point_bg: str
    canvas_label: str

    tab_bg: str
    tab_text: str
    tab_hover: str

    header_bg: str
    header_text: str

    menu_hover_bg: str
    menu_hover_text: str

    scrollbar_handle: str
    scrollbar_track: str


# ── Light theme ──────────────────────────────────────────────────────
LIGHT_THEME = Theme(
    name="light",
    primary="#0f62fe",
    primary_hover="#0a55df",
    primary_pressed="#0848c7",
    primary_soft="#eff6ff",
    primary_border="#bfdbfe",
    primary_text="#175cd3",
    text="#1f2937",
    text_strong="#0f172a",
    muted="#64748b",
    subtle="#475569",
    border="#d9e2ec",
    border_strong="#cfd8e3",
    surface="#ffffff",
    background="#eef2f7",
    panel="#f8fafc",
    panel_hover="#eef4ff",
    selection="#dbeafe",
    success_bg="#ecfdf3",
    success_border="#abefc6",
    success_text="#067647",
    error_bg="#fef3f2",
    error_border="#fecdca",
    error_text="#b42318",
    canvas_bg="#fcfcfd",
    canvas_title="#303030",
    canvas_arrow="#4d4d4d",
    canvas_placeholder_start=(220, 220, 220, 60),
    canvas_placeholder_end=(180, 180, 180, 90),
    canvas_grid="#d8d8d8",
    canvas_grid_bg="#fbfbfb",
    canvas_axis="#666666",
    canvas_data_line="#0f62fe",
    canvas_data_point_bg="#ffffff",
    canvas_label="#444444",
    tab_bg="#e9eef5",
    tab_text="#344054",
    tab_hover="#f6f8fc",
    header_bg="#f2f6fb",
    header_text="#344054",
    menu_hover_bg="#eaf1ff",
    menu_hover_text="#0f62fe",
    scrollbar_handle="#c4c9d4",
    scrollbar_track="#f1f3f5",
)

# ── Dark theme ───────────────────────────────────────────────────────
DARK_THEME = Theme(
    name="dark",
    primary="#448aff",
    primary_hover="#5c9aff",
    primary_pressed="#2f6fd9",
    primary_soft="#1a2740",
    primary_border="#2a4380",
    primary_text="#82b1ff",
    text="#d1d5db",
    text_strong="#e5e7eb",
    muted="#9ca3af",
    subtle="#6b7280",
    border="#3a3d45",
    border_strong="#4b4f59",
    surface="#1e2027",
    background="#14161b",
    panel="#252830",
    panel_hover="#2d3039",
    selection="#1e3a6e",
    success_bg="#0d2818",
    success_border="#1b5e30",
    success_text="#7ee0a0",
    error_bg="#2d1515",
    error_border="#7c2d2d",
    error_text="#f4a0a0",
    canvas_bg="#1a1c22",
    canvas_title="#c8ccd4",
    canvas_arrow="#6b7280",
    canvas_placeholder_start=(40, 42, 50, 100),
    canvas_placeholder_end=(30, 32, 40, 130),
    canvas_grid="#3a3d45",
    canvas_grid_bg="#18191e",
    canvas_axis="#9ca3af",
    canvas_data_line="#448aff",
    canvas_data_point_bg="#1e2027",
    canvas_label="#9ca3af",
    tab_bg="#22252c",
    tab_text="#9ca3af",
    tab_hover="#2a2e38",
    header_bg="#282c34",
    header_text="#d1d5db",
    menu_hover_bg="#1e3a6e",
    menu_hover_text="#448aff",
    scrollbar_handle="#4b4f59",
    scrollbar_track="#1e2027",
)

# ── Legacy colour aliases (light theme) – used by chat widgets, etc. ──
COLOR_PRIMARY = LIGHT_THEME.primary
COLOR_PRIMARY_HOVER = LIGHT_THEME.primary_hover
COLOR_PRIMARY_PRESSED = LIGHT_THEME.primary_pressed
COLOR_PRIMARY_SOFT = LIGHT_THEME.primary_soft
COLOR_PRIMARY_BORDER = LIGHT_THEME.primary_border
COLOR_PRIMARY_TEXT = LIGHT_THEME.primary_text
COLOR_TEXT = LIGHT_THEME.text
COLOR_TEXT_STRONG = LIGHT_THEME.text_strong
COLOR_MUTED = LIGHT_THEME.muted
COLOR_SUBTLE = LIGHT_THEME.subtle
COLOR_BORDER = LIGHT_THEME.border
COLOR_BORDER_STRONG = LIGHT_THEME.border_strong
COLOR_SURFACE = LIGHT_THEME.surface
COLOR_BACKGROUND = LIGHT_THEME.background
COLOR_PANEL = LIGHT_THEME.panel
COLOR_PANEL_HOVER = LIGHT_THEME.panel_hover
COLOR_SELECTION = LIGHT_THEME.selection
COLOR_SUCCESS_BG = LIGHT_THEME.success_bg
COLOR_SUCCESS_BORDER = LIGHT_THEME.success_border
COLOR_SUCCESS_TEXT = LIGHT_THEME.success_text
COLOR_ERROR_BG = LIGHT_THEME.error_bg
COLOR_ERROR_BORDER = LIGHT_THEME.error_border
COLOR_ERROR_TEXT = LIGHT_THEME.error_text

DARK_PRIMARY = DARK_THEME.primary
DARK_TEXT = DARK_THEME.text
DARK_MUTED = DARK_THEME.muted
DARK_SUBTLE = DARK_THEME.subtle
DARK_BORDER = DARK_THEME.border
DARK_BORDER_STRONG = DARK_THEME.border_strong
DARK_SURFACE = DARK_THEME.surface
DARK_BACKGROUND = DARK_THEME.background
DARK_PANEL = DARK_THEME.panel
DARK_PANEL_HOVER = DARK_THEME.panel_hover
DARK_SELECTION = DARK_THEME.selection
DARK_SUCCESS_BG = DARK_THEME.success_bg
DARK_SUCCESS_BORDER = DARK_THEME.success_border
DARK_SUCCESS_TEXT = DARK_THEME.success_text
DARK_ERROR_BG = DARK_THEME.error_bg
DARK_ERROR_BORDER = DARK_THEME.error_border
DARK_ERROR_TEXT = DARK_THEME.error_text

# ── Active theme ─────────────────────────────────────────────────────
_current_theme: Theme = LIGHT_THEME


def current_theme() -> Theme:
    """Return the currently active theme."""
    return _current_theme


def set_theme(name: str) -> None:
    """Switch the active theme by name ('light' or 'dark')."""
    global _current_theme
    if name == "dark":
        _current_theme = DARK_THEME
    else:
        _current_theme = LIGHT_THEME


def current_qss() -> str:
    """Return the full application QSS for the currently active theme."""
    t = _current_theme
    return f"""
            QMainWindow {{
                background: {t.background};
            }}
            QWidget {{
                color: {t.text};
                font-family: {FONT_FAMILY};
                font-size: 10pt;
            }}
            QLabel {{
                color: {t.text};
            }}
            QWidget#chatStreamWidget,
            QWidget#chatStreamContainer,
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollArea > QWidget > QWidget {{
                background: transparent;
                border: none;
            }}
            QFrame#ControllerStructureCanvas,
            QFrame#CurveCanvas,
            QTextEdit,
            QTableWidget,
            QTabWidget::pane,
            QMenu,
            QDialog,
            QWidget#panelCard {{
                background: {t.surface};
                border: 1px solid {t.border};
                border-radius: {RADIUS_CARD}px;
            }}
            QLabel#chatBubbleTitle {{
                font-size: 10pt;
                font-weight: 600;
                color: {t.muted};
            }}
            QLabel#chatBubbleBody {{
                font-size: 11pt;
                line-height: 1.55;
            }}
            QTabWidget::pane {{
                padding: 6px;
            }}
            QTabBar::tab {{
                background: {t.tab_bg};
                color: {t.tab_text};
                border: 1px solid {t.border_strong};
                border-bottom: none;
                border-top-left-radius: {RADIUS_CONTROL}px;
                border-top-right-radius: {RADIUS_CONTROL}px;
                min-width: 120px;
                padding: 8px 14px;
                margin-right: 4px;
            }}
            QTabBar::tab:selected {{
                background: {t.surface};
                color: {t.primary};
                font-weight: 600;
            }}
            QTabBar::tab:hover {{
                background: {t.tab_hover};
            }}
            QPushButton {{
                background: {t.surface};
                color: {t.text_strong};
                border: 1px solid {t.border_strong};
                border-radius: {RADIUS_CONTROL}px;
                padding: 7px 14px;
                min-height: 18px;
            }}
            QPushButton:hover {{
                background: {t.panel_hover};
                border-color: {t.primary_border};
            }}
            QPushButton:pressed {{
                background: {t.primary_soft};
            }}
            QPushButton#primaryButton {{
                background: {t.primary};
                color: white;
                border: none;
                font-weight: 600;
            }}
            QPushButton#primaryButton:hover {{
                background: {t.primary_hover};
            }}
            QPushButton#ghostButton,
            QPushButton#secondaryActionButton {{
                background: {t.panel};
                color: {t.text};
                border: 1px solid {t.border_strong};
                font-weight: 600;
            }}
            QPushButton#secondaryActionButton {{
                min-width: 112px;
            }}
            QPushButton#ghostButton:hover,
            QPushButton#secondaryActionButton:hover {{
                background: {t.panel_hover};
                border-color: {t.primary_border};
            }}
            QToolButton {{
                background: {t.surface};
                color: {t.text_strong};
                border: 1px solid {t.border_strong};
                border-radius: {RADIUS_CONTROL}px;
                padding: 7px 14px;
            }}
            QToolButton:hover {{
                background: {t.panel_hover};
                border-color: {t.primary_border};
            }}
            QTextEdit {{
                padding: 10px;
                selection-background-color: {t.selection};
                line-height: 1.4;
            }}
            QTableWidget {{
                gridline-color: {t.border};
                selection-background-color: {t.selection};
                selection-color: {t.text_strong};
            }}
            QHeaderView::section {{
                background: {t.header_bg};
                color: {t.header_text};
                border: none;
                border-bottom: 1px solid {t.border};
                padding: 8px 10px;
                font-weight: 600;
            }}
            QMenu {{
                border: 1px solid {t.border};
                padding: 6px;
            }}
            QMenu::item {{
                padding: 8px 24px 8px 18px;
                border-radius: {RADIUS_CONTROL}px;
                margin: 2px 0;
            }}
            QMenu::item:selected {{
                background: {t.menu_hover_bg};
                color: {t.menu_hover_text};
            }}
            QMessageBox {{
                background: {t.surface};
            }}
            QMessageBox QLabel {{
                color: {t.text};
                background: transparent;
            }}
            QDialog {{
                background: {t.background};
            }}
            QScrollBar:vertical {{
                background: {t.scrollbar_track};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {t.scrollbar_handle};
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar:horizontal {{
                background: {t.scrollbar_track};
                height: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:horizontal {{
                background: {t.scrollbar_handle};
                border-radius: 4px;
                min-width: 30px;
            }}
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
            """


# ── Legacy helpers (used by chat / tuning-result / etc.) ──


def transparent_qss() -> str:
    return "border:none;background:transparent;margin:0;padding:0;"


def surface_card_qss(object_name: str, radius: int = RADIUS_CARD) -> str:
    t = _current_theme
    return (
        f"QFrame#{object_name}{{background:{t.surface};border:1px solid {t.border};"
        f"border-radius:{radius}px;}}"
        f"QFrame#{object_name} QLabel{{border:none;background:transparent;}}"
    )


def primary_button_qss(
    radius: int = RADIUS_CONTROL,
    padding: str = "7px 14px",
    include_disabled: bool = True,
) -> str:
    t = _current_theme
    qss = (
        f"QPushButton{{background:{t.primary};color:white;border:none;"
        f"border-radius:{radius}px;font-weight:600;padding:{padding};}}"
        f"QPushButton:hover{{background:{t.primary_hover};}}"
        f"QPushButton:pressed{{background:{t.primary_pressed};}}"
    )
    if include_disabled:
        qss += "QPushButton:disabled{background:#6b7280;color:#d1d5db;}"
    return qss


def secondary_button_qss(radius: int = RADIUS_CONTROL, padding: str = "7px 14px") -> str:
    t = _current_theme
    return (
        f"QPushButton{{background:{t.panel};color:{t.text};border:1px solid {t.border_strong};"
        f"border-radius:{radius}px;font-weight:600;padding:{padding};}}"
        f"QPushButton:hover{{background:{t.panel_hover};border-color:{t.primary_border};}}"
        "QPushButton:disabled{color:#6b7280;}"
    )


def ghost_button_qss(radius: int = RADIUS_CONTROL, padding: str = "7px 14px") -> str:
    t = _current_theme
    return (
        f"QPushButton{{background:{t.surface};color:{t.muted};border:1px solid {t.border};"
        f"border-radius:{radius}px;font-weight:600;padding:{padding};}}"
        f"QPushButton:hover{{background:{t.panel};}}"
        "QPushButton:disabled{color:#6b7280;}"
    )


def flat_button_qss(radius: int = RADIUS_CONTROL, padding: str = "12px 24px") -> str:
    t = _current_theme
    return (
        f"QPushButton{{background:{t.panel};border:none;outline:none;border-radius:{radius}px;"
        f"padding:{padding};font-size:12pt;color:{t.text};}}"
        f"QPushButton:hover{{background:{t.panel_hover};}}"
        f"QPushButton:pressed{{background:{t.border};}}"
        "QPushButton:focus{outline:none;}"
    )


def status_label_qss() -> str:
    t = _current_theme
    return (
        f"QLabel#taskStatusLabel{{background:{t.panel};border:none;"
        f"border-radius:{RADIUS_CARD}px;padding:8px 10px;color:{t.subtle};}}"
    )


# ── Backwards-compatible aliases (called by MainWindow, etc.) ──


def app_qss() -> str:
    """Light-theme QSS (legacy name)."""
    set_theme("light")
    return current_qss()


def dark_qss() -> str:
    """Dark-theme QSS (legacy name)."""
    set_theme("dark")
    return current_qss()
