"""Shared font selection for Qt widgets, painters, and Matplotlib charts."""

from __future__ import annotations

from PyQt5.QtGui import QFont, QFontDatabase


# Keep this order aligned with Matplotlib.  The first installed family is used
# everywhere so text metrics do not drift between normal widgets and canvases.
UI_FONT_CANDIDATES = (
    "Microsoft YaHei UI",
    "Microsoft YaHei",
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "PingFang SC",
    "Segoe UI",
    "Arial",
)

MONOSPACE_FONT_CANDIDATES = (
    "Cascadia Mono",
    "Cascadia Code",
    "Consolas",
    "Noto Sans Mono CJK SC",
    "Microsoft YaHei UI",
)

# QSS accepts a comma-separated fallback list. Qt's application font is also
# resolved from this same candidate list at startup.
FONT_FAMILY_QSS = ", ".join(f'"{family}"' for family in UI_FONT_CANDIDATES) + ", sans-serif"
MONOSPACE_FONT_FAMILY_QSS = (
    ", ".join(f'"{family}"' for family in MONOSPACE_FONT_CANDIDATES) + ", monospace"
)


def _installed_families() -> dict[str, str]:
    """Map case-folded family names to Qt's canonical installed names."""
    return {family.casefold(): family for family in QFontDatabase().families()}


def resolve_font_family(candidates: tuple[str, ...] = UI_FONT_CANDIDATES) -> str:
    """Return the first installed candidate, falling back to Qt's default."""
    installed = _installed_families()
    for candidate in candidates:
        if candidate.casefold() in installed:
            return installed[candidate.casefold()]
    # Some platform plugins do not expose their font database during startup.
    # Naming a sensible family still lets Qt perform its normal substitution.
    return QFont().defaultFamily() or "Segoe UI"


def application_font(point_size: int = 10) -> QFont:
    """Build the single application-wide UI font."""
    font = QFont(resolve_font_family(), point_size)
    font.setStyleStrategy(QFont.PreferAntialias)
    return font


def configure_matplotlib_fonts(matplotlib_module) -> str:
    """Apply the shared UI font preference to Matplotlib and return its name."""
    import matplotlib.font_manager as font_manager

    available = {font.name.casefold(): font.name for font in font_manager.fontManager.ttflist}
    selected = next(
        (available[name.casefold()] for name in UI_FONT_CANDIDATES if name.casefold() in available),
        "sans-serif",
    )
    matplotlib_module.rcParams["font.family"] = [selected]
    matplotlib_module.rcParams["font.sans-serif"] = list(UI_FONT_CANDIDATES)
    matplotlib_module.rcParams["axes.unicode_minus"] = False
    return selected
