"""
Left panel: motor preset browser.

Scans <GMP_ROOT>/ctl/component/hardware_preset/pmsm_motor/*.h
and presents a searchable, selectable list.
"""

import os
from typing import Optional

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QFrame,
)

from core.parser import parse_motor_header, extract_preset_name, extract_brief_info


class PresetListItem:
    """Data container for one preset entry in the list."""

    def __init__(self, name: str, filepath: str, brief: str):
        self.name = name
        self.filepath = filepath
        self.brief = brief


class PresetListPanel(QWidget):
    """Left sidebar panel showing available presets."""

    preset_selected = pyqtSignal(str, dict)  # filepath, parsed_params

    def __init__(self, parent=None, title: str = "预设电机", search_placeholder: str = "搜索型号..."):
        super().__init__(parent)
        self._presets: list[PresetListItem] = []
        self._parsed_cache: dict[str, dict] = {}  # filepath → params
        self._gmp_root: str = ""
        self._title_text = title
        self._search_placeholder = search_placeholder
        self._parser_fn = None  # set by set_gmp_root / set_preset_dir
        self._brief_fn = None  # set by set_gmp_root / set_preset_dir
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Title
        title = QLabel(self._title_text)
        title.setObjectName("sectionHeader")
        layout.addWidget(title)

        # Search box
        self._search = QLineEdit()
        self._search.setObjectName("searchBox")
        self._search.setPlaceholderText(self._search_placeholder)
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search)

        # Preset list
        self._list = QListWidget()
        self._list.setObjectName("presetList")
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list.currentItemChanged.connect(self._on_item_changed)
        layout.addWidget(self._list)

        # Status hint
        self._status = QLabel("")
        self._status.setObjectName("emptyPlaceholder")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_gmp_root(self, path: str):
        """Set GMP root and reload the preset list (motor presets)."""
        from core.parser import parse_motor_header, extract_brief_info
        self._gmp_root = path
        self._parser_fn = parse_motor_header
        self._brief_fn = extract_brief_info
        self._parsed_cache.clear()
        preset_dir = os.path.join(
            path, "ctl", "component", "hardware_preset", "pmsm_motor"
        )
        self._load_presets(preset_dir)

    def set_preset_dir(self, path: str):
        """Set a custom preset directory and reload (board presets)."""
        from core.board_parser import parse_board_header, extract_board_brief
        self._parser_fn = parse_board_header
        self._brief_fn = extract_board_brief
        self._parsed_cache.clear()
        self._load_presets(path)

    def add_extra_preset(self, filepath: str):
        """Append a single file to the preset list (e.g. MONKEY_BOARD.h)."""
        if not os.path.isfile(filepath):
            return
        name = extract_preset_name(filepath)
        try:
            params = self._parser_fn(filepath) if self._parser_fn else {}
        except Exception:
            params = {}
        self._parsed_cache[filepath] = params
        brief = self._brief_fn(params) if self._brief_fn else ""
        self._presets.append(PresetListItem(name, filepath, brief))
        self._populate_list(self._presets)
        cnt = len(self._presets)
        self._status.setText(f"共 {cnt} 个预设")

    def current_preset_name(self) -> Optional[str]:
        """Return the name of the currently selected preset, if any."""
        item = self._list.currentItem()
        if item is None:
            return None
        idx = self._list.currentRow()
        if 0 <= idx < len(self._presets):
            return self._presets[idx].name
        return None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load_presets(self, preset_dir: str):
        """Scan the preset directory and populate the list."""
        self._presets.clear()
        self._list.clear()

        if not os.path.isdir(preset_dir):
            self._status.setText(f"未找到预设目录:\n{preset_dir}\n\n请在菜单栏设置 GMP 根目录。")
            return

        headers = sorted(
            [
                f
                for f in os.listdir(preset_dir)
                if f.endswith(".h") and not f.startswith("_")
            ]
        )

        if not headers:
            self._status.setText(f"预设目录为空:\n{preset_dir}")
            return

        for h in headers:
            filepath = os.path.join(preset_dir, h)
            name = extract_preset_name(filepath)
            try:
                if self._parser_fn:
                    params = self._parser_fn(filepath)
                else:
                    from core.parser import parse_motor_header
                    params = parse_motor_header(filepath)
                self._parsed_cache[filepath] = params
                brief = self._brief_fn(params) if self._brief_fn else ""
            except Exception:
                brief = ""
                self._parsed_cache[filepath] = {}

            self._presets.append(PresetListItem(name, filepath, brief))

        self._populate_list(self._presets)
        self._status.setText(f"共 {len(self._presets)} 个预设电机")

    def _populate_list(self, presets: list[PresetListItem]):
        """Fill the QListWidget with preset items."""
        self._list.blockSignals(True)
        self._list.clear()
        for p in presets:
            display = p.name
            if p.brief:
                display = f"{p.name}\n  {p.brief}"
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, p.filepath)
            self._list.addItem(item)
        self._list.blockSignals(False)

        if presets:
            self._list.setCurrentRow(0)

    def _on_search_changed(self, text: str):
        """Filter the list based on search text."""
        q = text.strip().lower()
        if not q:
            self._populate_list(self._presets)
            return
        filtered = [p for p in self._presets if q in p.name.lower()]
        self._populate_list(filtered)

    def _on_item_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        """Handle preset selection."""
        if current is None:
            return
        filepath = current.data(Qt.UserRole)
        params = self._parsed_cache.get(filepath, {})
        self.preset_selected.emit(filepath, params)
