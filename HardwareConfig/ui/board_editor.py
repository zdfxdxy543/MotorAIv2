"""
Driver board parameter editor.

Same 3-column inline-editable table style as the motor editor.
Handles string, float, and int parameter types.
"""

from typing import Optional, Union

from PyQt5.QtCore import pyqtSignal, Qt, QRegularExpression
from PyQt5.QtGui import QColor, QRegularExpressionValidator
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QLineEdit,
    QHeaderView,
    QFrame,
    QLabel,
)

from core.board_model import (
    BoardParamDef,
    BoardParamCategory,
    ParamKind,
    BOARD_PARAM_DEFS,
    BOARD_BY_CATEGORY,
    BOARD_CATEGORY_ORDER,
    BOARD_BY_MACRO,
)

COL_NAME = 0
COL_VALUE = 1
COL_UNIT = 2

CATEGORY_BG = QColor("#eef0f4")
CATEGORY_FG = QColor("#5f6b7a")
MUTED_FG = QColor("#8b909a")
PLACEHOLDER_FG = QColor("#c0c4cc")

ROLE_MACRO = Qt.UserRole


class BoardEditorPanel(QWidget):
    """Right panel: 3-column inline-editable table for driver board params."""

    param_changed = pyqtSignal(str, object)  # macro, float|int|str|None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._editors: dict[str, QLineEdit] = {}
        self._row_index: dict[str, int] = {}
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        title = QLabel("驱动板参数")
        title.setObjectName("sectionHeader")
        outer.addWidget(title)

        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["参数名称", "数值", "单位"])

        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(COL_NAME, QHeaderView.Stretch)
        hh.setSectionResizeMode(COL_VALUE, QHeaderView.Fixed)
        hh.setSectionResizeMode(COL_UNIT, QHeaderView.Fixed)
        self._table.setColumnWidth(COL_VALUE, 200)
        self._table.setColumnWidth(COL_UNIT, 90)

        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionMode(QTableWidget.NoSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setShowGrid(True)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setDefaultSectionSize(34)
        self._table.setFrameShape(QFrame.StyledPanel)

        self._populate_table()
        outer.addWidget(self._table)

    def _populate_table(self):
        self._table.setRowCount(0)
        self._editors.clear()
        self._row_index.clear()

        for cat in BOARD_CATEGORY_ORDER:
            self._add_category_row(cat)
            for pdef in BOARD_BY_CATEGORY[cat]:
                # Sub-label separator for circuit params
                if pdef.sub_label:
                    # Check if we need a sub-header
                    last_sub = getattr(self, "_last_sub_label", "")
                    if pdef.sub_label != last_sub:
                        self._add_sub_header(pdef.sub_label)
                        self._last_sub_label = pdef.sub_label
                self._add_param_row(pdef)

    def _add_category_row(self, cat: BoardParamCategory):
        r = self._table.rowCount()
        self._table.insertRow(r)
        item = QTableWidgetItem(cat.label)
        item.setFlags(Qt.NoItemFlags)
        item.setBackground(CATEGORY_BG)
        item.setForeground(CATEGORY_FG)
        f = item.font()
        f.setBold(True)
        item.setFont(f)
        self._table.setItem(r, COL_NAME, item)
        self._table.setSpan(r, COL_NAME, 1, 3)
        for c in (COL_VALUE, COL_UNIT):
            dummy = QTableWidgetItem("")
            dummy.setFlags(Qt.NoItemFlags)
            dummy.setBackground(CATEGORY_BG)
            self._table.setItem(r, c, dummy)
        self._table.setRowHeight(r, 26)
        self._last_sub_label = ""

    def _add_sub_header(self, label: str):
        r = self._table.rowCount()
        self._table.insertRow(r)
        item = QTableWidgetItem(f"  {label}")
        item.setFlags(Qt.NoItemFlags)
        item.setForeground(QColor("#8b909a"))
        f = item.font()
        f.setItalic(True)
        item.setFont(f)
        self._table.setItem(r, COL_NAME, item)
        self._table.setSpan(r, COL_NAME, 1, 3)
        for c in (COL_VALUE, COL_UNIT):
            dummy = QTableWidgetItem("")
            dummy.setFlags(Qt.NoItemFlags)
            self._table.setItem(r, c, dummy)
        self._table.setRowHeight(r, 22)

    def _add_param_row(self, pdef: BoardParamDef):
        r = self._table.rowCount()
        self._table.insertRow(r)
        self._row_index[pdef.macro] = r

        # Col 0 — name
        name_text = f"{pdef.label}  ({pdef.symbol})" if pdef.symbol else pdef.label
        name = QTableWidgetItem(name_text)
        name.setFlags(Qt.ItemIsEnabled)
        self._table.setItem(r, COL_NAME, name)

        # Col 1 — editor
        editor = QLineEdit()
        editor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        editor.setFrame(False)
        editor.setPlaceholderText("—")
        editor.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                padding: 2px 6px;
                font-family: "Consolas", "Cascadia Code", monospace;
                font-size: 13px;
                color: #1a1a2e;
            }
        """)
        if pdef.kind == ParamKind.STRING:
            # Allow any text
            pass
        elif pdef.kind == ParamKind.INT:
            rx = QRegularExpression(r"^-?\d+$")
            editor.setValidator(QRegularExpressionValidator(rx, editor))
        else:
            rx = QRegularExpression(r"^-?\d*\.?\d*(?:[eE][+-]?\d+)?$")
            editor.setValidator(QRegularExpressionValidator(rx, editor))

        editor.editingFinished.connect(
            lambda m=pdef.macro, e=editor: self._on_editor_finished(m, e)
        )
        self._editors[pdef.macro] = editor
        self._table.setCellWidget(r, COL_VALUE, editor)

        # Col 2 — unit
        unit = QTableWidgetItem(pdef.unit)
        unit.setFlags(Qt.ItemIsEnabled)
        unit.setForeground(MUTED_FG)
        unit.setTextAlignment(Qt.AlignCenter)
        self._table.setItem(r, COL_UNIT, unit)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_params(self, params: dict[str, Optional[Union[float, int, str]]]):
        for macro, editor in self._editors.items():
            val = params.get(macro)
            self._set_editor_value(editor, val)

    def get_all_params(self) -> dict[str, Optional[Union[float, int, str]]]:
        result: dict[str, Optional[Union[float, int, str]]] = {}
        for macro, editor in self._editors.items():
            result[macro] = self._editor_value(macro, editor)
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _editor_value(self, macro: str, editor: QLineEdit) -> Optional[Union[float, int, str]]:
        pdef = self._find_def(macro)
        text = editor.text().strip()
        if not text:
            return None
        if pdef and pdef.kind == ParamKind.STRING:
            return text
        if pdef and pdef.kind == ParamKind.INT:
            try:
                return int(text)
            except ValueError:
                return None
        try:
            return float(text)
        except ValueError:
            return None

    def _set_editor_value(self, editor: QLineEdit, value):
        if value is None:
            editor.setText("")
        elif isinstance(value, str):
            editor.setText(value)
        elif isinstance(value, bool):
            editor.setText(str(int(value)))
        elif isinstance(value, int):
            editor.setText(str(value))
        elif isinstance(value, float):
            # Check if this is an int-kind param → format as int
            for macro, ed in self._editors.items():
                if ed is editor:
                    pdef = BOARD_BY_MACRO.get(macro)
                    if pdef and pdef.kind == ParamKind.INT:
                        editor.setText(str(int(value)))
                        return
                    break
            editor.setText(self._format_number(value))
        else:
            editor.setText(str(value))

    def _is_float_param(self, editor: QLineEdit) -> bool:
        for macro, ed in self._editors.items():
            if ed is editor:
                pdef = self._find_def(macro)
                return pdef is not None and pdef.kind == ParamKind.FLOAT
        return True

    def _find_def(self, macro: str) -> Optional[BoardParamDef]:
        return BOARD_BY_MACRO.get(macro)

    @staticmethod
    def _format_number(val: float) -> str:
        if abs(val) >= 1e6 or (0 < abs(val) < 1e-4):
            return f"{val:.6e}"
        s = f"{val:.6f}".rstrip("0")
        if s.endswith("."):
            s += "0"
        return s

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_editor_finished(self, macro: str, editor: QLineEdit):
        val = self._editor_value(macro, editor)
        self.param_changed.emit(macro, val)
