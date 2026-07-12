"""History panel — recent projects list + selected project info.

History is persisted in a single JSON file.  On refresh, entries whose project
JSON no longer exists on disk are removed automatically.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable

from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PyQt5.QtCore import Qt

import core.paths  # ensures repository roots are on sys.path
from core.paths import MOTORAI_ROOT
from styles.theme import current_theme

HISTORY_FILE = MOTORAI_ROOT / "Generate" / "ui" / "history.json"


# ── history storage ──────────────────────────────────────────────────

def load_history() -> list[dict]:
    """Return list of history entries, removing any whose project no longer exists."""
    if not HISTORY_FILE.exists():
        return []

    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return []

    entries = data.get("entries") if isinstance(data, dict) else []
    if not isinstance(entries, list):
        return []

    valid: list[dict] = []
    changed = False
    for entry in entries:
        if not isinstance(entry, dict):
            changed = True
            continue
        path_str = entry.get("path")
        if not isinstance(path_str, str) or not path_str.strip():
            changed = True
            continue
        if not Path(path_str).exists():
            changed = True
            continue
        valid.append(entry)

    if changed:
        _save_entries(valid)

    return valid


def _save_entries(entries: list[dict]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(
        json.dumps({"entries": entries}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add_to_history(json_path: Path | str) -> None:
    """Add or update a project in the history file."""
    json_path = Path(json_path).expanduser().resolve()
    if not json_path.exists():
        return

    entries = load_history()
    path_str = str(json_path)

    # Try to read the project name from the JSON.
    name = json_path.parent.name
    try:
        data = json.loads(json_path.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            name = data.get("project_name") or name
    except Exception:
        pass

    # Update existing or append new.
    for entry in entries:
        if entry.get("path") == path_str:
            entry["name"] = name
            entry["last_opened"] = time.time()
            _save_entries(entries)
            return

    entries.append({"name": name, "path": path_str, "last_opened": time.time()})
    _save_entries(entries)


# ── panel widget ─────────────────────────────────────────────────────

class HistoryPanel(QWidget):
    """Left sidebar: project list (top) + project details (bottom)."""

    def __init__(
        self,
        on_project_selected: Callable[[Path], None] | None = None,
        on_project_opened: Callable[[Path], None] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._on_project_selected = on_project_selected
        self._on_project_opened = on_project_opened

        t = current_theme()
        self.setObjectName('historyPanel')
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f'QWidget#historyPanel{{background:{t.panel};border:none;}}')

        # ── project list ──────────────────────────────────────────
        self.project_list = QListWidget()
        self.project_list.setFrameShape(QFrame.NoFrame)
        self.project_list.itemClicked.connect(self._on_item_clicked)
        self.project_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.project_list.setStyleSheet(
            f"QListWidget{{background:{t.panel};border:none;outline:none;}}"
            f"QListWidget::item{{padding:6px 8px;border:none;border-radius:6px;}}"
            f"QListWidget::item:selected{{background:{t.selection};color:{t.text_strong};}}"
            f"QListWidget::item:hover{{background:{t.panel_hover};}}"
        )

        list_header = QWidget()
        list_header.setAttribute(Qt.WA_StyledBackground, True)
        list_header.setStyleSheet(f'background:{t.panel};border:none;')
        list_header_layout = QHBoxLayout(list_header)
        list_header_layout.setContentsMargins(8, 4, 8, 4)
        title_label = QLabel("历史工程")  # 历史工程
        title_label.setStyleSheet(f'font-size:14px;font-weight:600;color:{t.muted};')
        list_header_layout.addWidget(title_label)

        # ── project info ──────────────────────────────────────────
        self.info_scroll = QScrollArea()
        self.info_scroll.setWidgetResizable(True)
        self.info_scroll.setFrameShape(QFrame.NoFrame)
        self.info_scroll.setStyleSheet(
            f'QScrollArea{{background:{t.panel};border:none;}}'
            f'QScrollArea > QWidget > QWidget{{background:{t.panel};}}'
        )

        info_body = QWidget()
        info_body.setStyleSheet(f'background:{t.panel};border:none;')
        info_body_layout = QVBoxLayout(info_body)
        info_body_layout.setContentsMargins(8, 8, 8, 8)

        self.info_empty_label = QLabel('单击历史工程查看详情')
        self.info_empty_label.setAlignment(Qt.AlignCenter)
        self.info_empty_label.setWordWrap(True)
        self.info_empty_label.setStyleSheet(f'font-size:12px;color:{t.muted};padding:20px 8px;')
        info_body_layout.addWidget(self.info_empty_label)

        self.info_card = QFrame()
        self.info_card.setObjectName('projectInfoCard')
        self.info_card.setStyleSheet(
            f'QFrame#projectInfoCard{{background:{t.surface};border:1px solid {t.border};border-radius:8px;}}'
            f'QFrame#projectInfoCard QLabel{{background:transparent;border:none;}}'
        )
        card_layout = QVBoxLayout(self.info_card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(0)
        self.info_value_labels = {}
        fields = (
            ('candidate_count', '候选方案数'),
            ('max_iterations', '最大迭代'),
            ('task_type', '任务类型'),
            ('objective', '设计目标'),
            ('design_profile', '设计方案'),
            ('path', '项目位置'),
        )
        for index, (key, caption) in enumerate(fields):
            row = QWidget()
            row.setStyleSheet('background:transparent;border:none;')
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 8, 0, 8)
            row_layout.setSpacing(10)

            caption_label = QLabel(caption)
            caption_label.setFixedWidth(68)
            caption_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            caption_label.setStyleSheet(f'font-size:12px;color:{t.muted};')
            row_layout.addWidget(caption_label)

            value_label = QLabel('—')
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            value_label.setStyleSheet(f'font-size:13px;font-weight:400;color:{t.text};')
            row_layout.addWidget(value_label, 1)
            self.info_value_labels[key] = value_label
            card_layout.addWidget(row)

            if index < len(fields) - 1:
                divider = QFrame()
                divider.setFrameShape(QFrame.HLine)
                divider.setStyleSheet(f'background:{t.border};border:none;max-height:1px;')
                card_layout.addWidget(divider)

        self.info_card.hide()
        info_body_layout.addWidget(self.info_card)
        info_body_layout.addStretch()
        self.info_scroll.setWidget(info_body)

        info_header = QWidget()
        info_header.setAttribute(Qt.WA_StyledBackground, True)
        info_header.setStyleSheet(f'background:{t.panel};border:none;')
        info_header_layout = QHBoxLayout(info_header)
        info_header_layout.setContentsMargins(8, 4, 8, 4)
        info_label = QLabel("项目信息")  # 项目信息
        info_label.setStyleSheet(f'font-size:14px;font-weight:600;color:{t.muted};')
        info_header_layout.addWidget(info_label)

        # ── splitter ──────────────────────────────────────────────
        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)

        list_container = QWidget()
        list_container.setAttribute(Qt.WA_StyledBackground, True)
        list_container.setStyleSheet(f'background:{t.panel};border:none;')
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(0)
        list_layout.addWidget(list_header)
        list_layout.addWidget(self.project_list)

        info_container = QWidget()
        info_container.setAttribute(Qt.WA_StyledBackground, True)
        info_container.setStyleSheet(f'background:{t.panel};border:none;')
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(0)
        info_layout.addWidget(info_header)
        info_layout.addWidget(self.info_scroll)

        splitter.addWidget(list_container)
        splitter.addWidget(info_container)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(splitter)

    # ── public API ───────────────────────────────────────────────────

    def refresh(self) -> None:
        """Reload history from the JSON file (stale entries auto-removed)."""
        self.project_list.clear()

        for entry in load_history():
            name = entry.get("name") or "unknown"
            path_str = entry.get("path") or ""
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, path_str)
            self.project_list.addItem(item)

    # ── slots ────────────────────────────────────────────────────────

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        path_str = item.data(Qt.UserRole)
        if not path_str:
            return
        path = Path(path_str)
        self._show_info(path)
        if self._on_project_selected:
            self._on_project_selected(path)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        path_str = item.data(Qt.UserRole)
        if not path_str:
            return
        path = Path(path_str)
        if self._on_project_opened:
            self._on_project_opened(path)

    def _show_info(self, json_path: Path) -> None:
        try:
            data = json.loads(json_path.read_text(encoding="utf-8-sig"))
        except Exception:
            self.info_card.hide()
            self.info_empty_label.setText('无法读取项目文件')
            self.info_empty_label.show()
            return

        objective = data.get('objective')
        objective = objective.strip() if isinstance(objective, str) and objective.strip() else '—'
        profile = data.get('design_profile')
        profile_name = profile.get('name') if isinstance(profile, dict) else ''
        values = {
            'candidate_count': data.get('candidate_count', '—'),
            'max_iterations': data.get('max_iterations', '—'),
            'task_type': data.get('task_type') or '—',
            'objective': objective,
            'design_profile': profile_name or '—',
            'path': str(json_path.parent),
        }
        for key, value in values.items():
            text = str(value)
            self.info_value_labels[key].setText(text)
            self.info_value_labels[key].setToolTip(text if key == 'path' else '')

        self.info_empty_label.hide()
        self.info_card.show()
