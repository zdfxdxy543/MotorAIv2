"""
HardwareConfig main window.

Tab-switchable editor: 电机参数 / 驱动板参数.
Each tab has its own preset list (left) and parameter table (right).
"""

import os
import json
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QSplitter,
    QStackedWidget,
    QMenuBar,
    QAction,
    QFileDialog,
    QMessageBox,
    QStatusBar,
    QPushButton,
    QLabel,
    QLineEdit,
    QToolBar,
    QSizePolicy,
    QButtonGroup,
    QHBoxLayout,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
)

from ui.styles import app_stylesheet
from ui.preset_list import PresetListPanel
from ui.param_editor import ParamEditorPanel
from ui.board_editor import BoardEditorPanel
from core.parser import parse_motor_header
from core.board_parser import parse_board_header
from core.generator import generate_motor_model, generate_board_model

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

TAB_MOTOR = 0
TAB_BOARD = 1


def _load_config() -> dict:
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            pass
    return {}


def _save_config(cfg: dict):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MotorAI — 硬件配置")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)

        self._gmp_root: str = ""
        self._output_path_motor: str = ""
        self._output_path_board: str = ""
        self._current_tab: int = TAB_MOTOR

        self._build_menu()
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()
        self._apply_style()

        cfg = _load_config()
        gmp_root = cfg.get("gmp_root", "")
        if gmp_root and os.path.isdir(gmp_root):
            self._gmp_root = gmp_root
            self._on_gmp_root_ready()
        # 不再自动弹窗选择目录，用户可通过菜单打开设置对话框

        self._output_path_motor = cfg.get("output_dir_motor", "")
        self._output_path_board = cfg.get("output_dir_board", "")

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_menu(self):
        mb = self.menuBar()
        file_menu = mb.addMenu("文件(&F)")
        set_gmp = QAction("设置 GMP 根目录...", self)
        set_gmp.triggered.connect(self._show_gmp_settings_dialog)
        file_menu.addAction(set_gmp)
        file_menu.addSeparator()
        quit_action = QAction("退出(&Q)", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    def _build_toolbar(self):
        tb = QToolBar("生成")
        tb.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, tb)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)

        tb.addWidget(QLabel("输出路径:"))

        self._output_edit = QLineEdit()
        self._output_edit.setPlaceholderText("选择输出位置...")
        self._output_edit.setMinimumWidth(320)
        self._output_edit.setMaximumWidth(500)
        self._output_edit.setObjectName("searchBox")
        tb.addWidget(self._output_edit)

        browse_btn = QPushButton("浏览")
        browse_btn.setObjectName("secondaryButton")
        browse_btn.clicked.connect(self._browse_output)
        tb.addWidget(browse_btn)

        tb.addSeparator()

        self._generate_btn = QPushButton("生成 Motor_Model.h")
        self._generate_btn.setObjectName("primaryButton")
        self._generate_btn.clicked.connect(self._generate)
        tb.addWidget(self._generate_btn)

    def _build_central(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(8)

        # ---- Tab buttons ----
        tab_row = QHBoxLayout()
        tab_row.setContentsMargins(0, 0, 0, 0)
        tab_row.setSpacing(0)

        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)

        self._btn_motor = QPushButton("电机参数")
        self._btn_motor.setCheckable(True)
        self._btn_motor.setChecked(True)
        self._btn_motor.setObjectName("tabButton")
        self._btn_motor.clicked.connect(lambda: self._switch_tab(TAB_MOTOR))
        self._tab_group.addButton(self._btn_motor, TAB_MOTOR)

        self._btn_board = QPushButton("驱动板参数")
        self._btn_board.setCheckable(True)
        self._btn_board.setObjectName("tabButton")
        self._btn_board.clicked.connect(lambda: self._switch_tab(TAB_BOARD))
        self._tab_group.addButton(self._btn_board, TAB_BOARD)

        tab_row.addWidget(self._btn_motor)
        tab_row.addWidget(self._btn_board)
        tab_row.addStretch()
        root.addLayout(tab_row)

        # ---- Splitter with stacked panels ----
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)

        # Left stack: preset lists
        self._left_stack = QStackedWidget()
        self._motor_presets = PresetListPanel()
        self._motor_presets.preset_selected.connect(self._on_motor_preset)
        self._board_presets = PresetListPanel()
        self._board_presets.preset_selected.connect(self._on_board_preset)
        self._left_stack.addWidget(self._motor_presets)
        self._left_stack.addWidget(self._board_presets)
        splitter.addWidget(self._left_stack)

        # Right stack: editors
        self._right_stack = QStackedWidget()
        self._motor_editor = ParamEditorPanel()
        self._motor_editor.param_changed.connect(self._on_motor_param)
        self._board_editor = BoardEditorPanel()
        self._board_editor.param_changed.connect(self._on_board_param)
        self._right_stack.addWidget(self._motor_editor)
        self._right_stack.addWidget(self._board_editor)
        splitter.addWidget(self._right_stack)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([280, 900])
        root.addWidget(splitter)

    def _build_statusbar(self):
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("请通过 文件 → 设置 GMP 根目录 进行配置。")

    def _apply_style(self):
        self.setStyleSheet(app_stylesheet())

    # ------------------------------------------------------------------
    # Tab switching
    # ------------------------------------------------------------------

    def _switch_tab(self, tab: int):
        self._current_tab = tab
        self._left_stack.setCurrentIndex(tab)
        self._right_stack.setCurrentIndex(tab)

        if tab == TAB_MOTOR:
            self._generate_btn.setText("生成 Motor_Model.h")
            self._output_edit.setText(self._output_path_motor)
        else:
            self._generate_btn.setText("生成 Driver_Board.h")
            self._output_edit.setText(self._output_path_board)

    # ------------------------------------------------------------------
    # GMP root
    # ------------------------------------------------------------------

    def _show_gmp_settings_dialog(self):
        """弹出 GMP 根目录设置对话框（输入框 + 浏览按钮）。"""
        dlg = QDialog(self)
        dlg.setWindowTitle("设置 GMP 根目录")
        dlg.resize(520, 100)
        dlg.setObjectName("SettingsDialog")

        layout = QVBoxLayout(dlg)
        form = QFormLayout()

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        gmp_edit = QLineEdit()
        gmp_edit.setPlaceholderText("请选择或输入 GMP 根目录")
        gmp_edit.setText(self._gmp_root)

        def browse():
            path = QFileDialog.getExistingDirectory(dlg, "选择 GMP 根目录", gmp_edit.text() or os.getcwd())
            if path:
                gmp_edit.setText(path)

        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(browse)

        row_layout.addWidget(gmp_edit)
        row_layout.addWidget(browse_btn)
        form.addRow("GMP根目录", row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(lambda: self._on_gmp_settings_accepted(gmp_edit.text().strip(), dlg))
        buttons.rejected.connect(dlg.reject)

        layout.addLayout(form)
        layout.addWidget(buttons)
        dlg.exec_()

    def _on_gmp_settings_accepted(self, path: str, dlg: QDialog):
        if not path:
            QMessageBox.warning(dlg, "提示", "请输入或选择 GMP 根目录。")
            return
        if not os.path.isdir(path):
            QMessageBox.warning(dlg, "提示", f"目录不存在：\n{path}")
            return
        self._gmp_root = path
        self._on_gmp_root_ready()
        cfg = _load_config()
        cfg["gmp_root"] = path
        _save_config(cfg)
        self._status.showMessage(f"GMP 根目录: {path}")
        dlg.accept()

    def _on_gmp_root_ready(self):
        """Notify both preset lists of the GMP root."""
        self._motor_presets.set_gmp_root(self._gmp_root)
        # Board presets: scan inverter_3ph directory + extra standalone files
        board_dir = os.path.join(
            self._gmp_root, "ctl", "component", "hardware_preset", "inverter_3ph"
        )
        self._board_presets.set_preset_dir(board_dir)
        # Add MONKEY_BOARD.h from GMP root (and ctl/ as fallback)
        for extra in [
            os.path.join(self._gmp_root, "MONKEY_BOARD.h"),
            os.path.join(self._gmp_root, "ctl", "MONKEY_BOARD.h"),
        ]:
            if os.path.isfile(extra):
                self._board_presets.add_extra_preset(extra)

    # ------------------------------------------------------------------
    # Output path
    # ------------------------------------------------------------------

    def _browse_output(self):
        if self._current_tab == TAB_MOTOR:
            default = self._output_path_motor or os.path.join(self._gmp_root or os.getcwd(), "Motor_Model.h")
            title = "保存 Motor_Model.h"
        else:
            default = self._output_path_board or os.path.join(self._gmp_root or os.getcwd(), "Driver_Board.h")
            title = "保存 Driver_Board.h"

        path, _ = QFileDialog.getSaveFileName(
            self, title, default, "Header files (*.h);;All files (*)"
        )
        if path:
            if self._current_tab == TAB_MOTOR:
                self._output_path_motor = path
            else:
                self._output_path_board = path
            self._output_edit.setText(path)

    # ------------------------------------------------------------------
    # Preset selection
    # ------------------------------------------------------------------

    def _on_motor_preset(self, filepath: str, params: dict):
        self._motor_editor.load_params(params)
        name = os.path.splitext(os.path.basename(filepath))[0]
        self._status.showMessage(f"已加载电机预设: {name}")

    def _on_board_preset(self, filepath: str, params: dict):
        self._board_editor.load_params(params)
        name = os.path.splitext(os.path.basename(filepath))[0]
        self._status.showMessage(f"已加载驱动板预设: {name}")

    # ------------------------------------------------------------------
    # Param changes
    # ------------------------------------------------------------------

    def _on_motor_param(self, macro: str, value):
        pass

    def _on_board_param(self, macro: str, value):
        pass

    # ------------------------------------------------------------------
    # Generate
    # ------------------------------------------------------------------

    def _generate(self):
        if self._current_tab == TAB_MOTOR:
            self._generate_motor()
        else:
            self._generate_board()

    def _generate_motor(self):
        output = self._output_path_motor
        if not output:
            self._browse_output()
            output = self._output_path_motor
            if not output:
                return

        params = self._motor_editor.get_all_params()
        preset = self._motor_presets.current_preset_name() or ""

        try:
            generate_motor_model(params, output, preset_name=preset)
            QMessageBox.information(self, "生成完成", f"Motor_Model.h 已保存至:\n{output}")
            self._status.showMessage(f"已生成: {output}")
            cfg = _load_config()
            cfg["output_dir_motor"] = output
            _save_config(cfg)
        except Exception as e:
            QMessageBox.critical(self, "生成失败", f"无法写入文件:\n{e}")

    def _generate_board(self):
        output = self._output_path_board
        if not output:
            self._browse_output()
            output = self._output_path_board
            if not output:
                return

        params = self._board_editor.get_all_params()
        preset = self._board_presets.current_preset_name() or ""

        try:
            generate_board_model(params, output, preset_name=preset)
            QMessageBox.information(self, "生成完成", f"Driver_Board.h 已保存至:\n{output}")
            self._status.showMessage(f"已生成: {output}")
            cfg = _load_config()
            cfg["output_dir_board"] = output
            _save_config(cfg)
        except Exception as e:
            QMessageBox.critical(self, "生成失败", f"无法写入文件:\n{e}")

    # ------------------------------------------------------------------

    def closeEvent(self, event):
        cfg = _load_config()
        cfg["gmp_root"] = self._gmp_root
        cfg["output_dir_motor"] = self._output_path_motor
        cfg["output_dir_board"] = self._output_path_board
        _save_config(cfg)
        super().closeEvent(event)
