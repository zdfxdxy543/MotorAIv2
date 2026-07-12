from PyQt5.QtWidgets import (
    QAction,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from PyQt5.QtCore import (
    QEasingCurve,
    QPoint,
    QProcess,
    QPropertyAnimation,
    Qt,
    QTimer,
    pyqtProperty,
    pyqtSignal,
)
from PyQt5.QtGui import QColor, QIcon
import json
import os
import subprocess
import sys
from pathlib import Path

from core.paths import MOTORAI_ROOT
from motorai_config import get_output_root, load_settings
from dialogs.project import NewProjectDialog, SettingsDialog
from panels.controller_structure import ControllerStructurePanel
from panels.cosim_config import CandidateNetworkPanel
from panels.history import HistoryPanel, add_to_history
from panels.result_charts import ResultChartsPanel
from panels.tuning_result import TuningResultPanel
from panels.workspace import Design3RightPanel
from styles.theme import (
    app_qss,
    current_theme,
    dark_qss,
    primary_button_qss,
)


def _short_id(candidate_id: str) -> str:
    """candidate_01 → C01"""
    import re
    m = re.match(r'candidate_(\d+)$', str(candidate_id))
    return f'C{m.group(1)}' if m else str(candidate_id)


class DrawerHandle(QFrame):
    clicked = pyqtSignal()

    def __init__(self, side: str, label: str, parent=None):
        super().__init__(parent)
        self.side = side
        self.label = label
        self._expanded = True
        self.setObjectName('drawerHandle')
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedWidth(12)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.grip = QFrame()
        self.grip.setObjectName('drawerHandleGrip')
        self.grip.setFixedSize(3, 40)
        layout.addWidget(self.grip, 0, Qt.AlignCenter)

        self._apply_style()
        self.set_expanded(True)

    def _apply_style(self):
        t = current_theme()
        self.setStyleSheet(
            'QFrame#drawerHandle{background:transparent;border:none;}'
            f'QFrame#drawerHandle:hover{{background:{t.primary_soft};}}'
            f'QFrame#drawerHandleGrip{{background:{t.border_strong};border:none;border-radius:1px;}}'
        )

    def set_expanded(self, expanded: bool):
        self._expanded = expanded
        action = '收起' if expanded else '展开'
        self.setToolTip(f'{action}{self.label}')

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            event.accept()
            self.clicked.emit()
            return
        super().mousePressEvent(event)


class CenterInsetHost(QWidget):
    def __init__(self, center_widget: QWidget, parent=None):
        super().__init__(parent)
        self._left_inset = 0
        self._right_inset = 0

        self.setObjectName('centerInsetHost')
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f'QWidget#centerInsetHost{{background:{current_theme().surface};border:none;}}')

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.addWidget(center_widget)

        self._left_animation = QPropertyAnimation(self, b'leftInset', self)
        self._right_animation = QPropertyAnimation(self, b'rightInset', self)
        for animation in (self._left_animation, self._right_animation):
            animation.setDuration(240)
            animation.setEasingCurve(QEasingCurve.OutCubic)

    def set_target_insets(self, left: int, right: int, animated: bool):
        left = max(0, int(left))
        right = max(0, int(right))

        if not animated:
            self._left_animation.stop()
            self._right_animation.stop()
            self.leftInset = left
            self.rightInset = right
            return

        self._animate_inset(self._left_animation, self.leftInset, left)
        self._animate_inset(self._right_animation, self.rightInset, right)

    @staticmethod
    def _animate_inset(animation: QPropertyAnimation, start: int, end: int):
        animation.stop()
        animation.setStartValue(start)
        animation.setEndValue(end)
        animation.start()

    def _apply_insets(self):
        self._layout.setContentsMargins(self._left_inset, 0, self._right_inset, 0)

    def _get_left_inset(self) -> int:
        return self._left_inset

    def _set_left_inset(self, value: int):
        self._left_inset = max(0, int(value))
        self._apply_insets()

    def _get_right_inset(self) -> int:
        return self._right_inset

    def _set_right_inset(self, value: int):
        self._right_inset = max(0, int(value))
        self._apply_insets()

    leftInset = pyqtProperty(int, _get_left_inset, _set_left_inset)
    rightInset = pyqtProperty(int, _get_right_inset, _set_right_inset)


class FloatingDrawer(QFrame):
    expandedChanged = pyqtSignal(bool)

    def __init__(self, side: str, content: QWidget, label: str, preferred_width: int, parent=None):
        super().__init__(parent)
        self.side = side
        self.content = content
        self.label = label
        self.preferred_width = preferred_width
        self.handle_width = 12
        self._content_width = preferred_width
        self._expanded = True

        self.setObjectName(f'{side}FloatingDrawer')
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet('QFrame{background:transparent;border:none;}')

        self.content.setParent(self)
        self.content.show()

        self.handle = DrawerHandle(side, label, self)
        self.handle.clicked.connect(self.toggle)

        self._animation = QPropertyAnimation(self, b'pos', self)
        self._animation.setDuration(240)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(26)
        shadow.setOffset(5 if side == 'left' else -5, 0)
        shadow.setColor(QColor(15, 23, 42, 42))
        self.setGraphicsEffect(shadow)

    def toggle(self):
        self.set_expanded(not self._expanded, animated=True)

    def set_expanded(self, expanded: bool, animated: bool = True):
        changed = self._expanded != expanded
        self._expanded = expanded
        self.handle.set_expanded(expanded)
        self.raise_()

        target = QPoint(self._target_x(), 0)
        if not animated:
            self._animation.stop()
            self.move(target)
            if changed:
                self.expandedChanged.emit(expanded)
            return

        self._animation.stop()
        self._animation.setStartValue(self.pos())
        self._animation.setEndValue(target)
        self._animation.start()
        if changed:
            self.expandedChanged.emit(expanded)

    def sync_geometry(self, parent_width: int, parent_height: int):
        self._content_width = self._resolve_content_width(parent_width)
        total_width = self._content_width + self.handle_width
        self.resize(total_width, parent_height)

        if self.side == 'left':
            self.content.setGeometry(0, 0, self._content_width, parent_height)
            self.handle.setGeometry(self._content_width, 0, self.handle_width, parent_height)
        else:
            self.handle.setGeometry(0, 0, self.handle_width, parent_height)
            self.content.setGeometry(self.handle_width, 0, self._content_width, parent_height)

        self.set_expanded(self._expanded, animated=False)

    def _resolve_content_width(self, parent_width: int) -> int:
        if self.side == 'left':
            if parent_width < 860:
                return max(180, min(210, int(parent_width * 0.24)))
            if parent_width < 1200:
                return max(200, min(230, int(parent_width * 0.20)))
            return max(240, min(280, int(parent_width * 0.20), self.preferred_width))
        # 右侧面板：展开后覆盖半个屏幕
        return max(320, parent_width // 2)

    def _target_x(self) -> int:
        parent = self.parentWidget()
        parent_width = parent.width() if parent is not None else self.width()
        if self.side == 'left':
            return 0 if self._expanded else -self._content_width
        return parent_width - self.width() if self._expanded else parent_width - self.handle_width

    def content_width(self) -> int:
        return self._content_width

    def is_expanded(self) -> bool:
        return self._expanded


class OverlayWorkspace(QWidget):
    def __init__(self, center_widget: QWidget, left_widget: QWidget, right_widget: QWidget, parent=None):
        super().__init__(parent)
        self.setObjectName('overlayWorkspace')
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f'QWidget#overlayWorkspace{{background:{current_theme().surface};border:none;}}')

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.center_host = CenterInsetHost(center_widget, self)
        layout.addWidget(self.center_host)

        self.left_drawer = FloatingDrawer('left', left_widget, '历史栏', 280, self)
        self.right_drawer = FloatingDrawer('right', right_widget, '结果栏', 400, self)
        self.left_drawer.expandedChanged.connect(lambda _expanded: self._sync_center_insets(animated=True))
        self.right_drawer.expandedChanged.connect(lambda _expanded: self._sync_center_insets(animated=True))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.left_drawer.sync_geometry(self.width(), self.height())
        self.right_drawer.sync_geometry(self.width(), self.height())
        self._sync_center_insets(animated=False)
        self.left_drawer.raise_()
        self.right_drawer.raise_()

    def _sync_center_insets(self, animated: bool):
        gap = 8
        left = self._reserved_width(self.left_drawer, gap)
        # 右侧面板以覆盖方式展示，中间内容只预留 handle 的窄条空间
        right = self.right_drawer.handle_width + gap
        self.center_host.set_target_insets(left, right, animated=animated)

    @staticmethod
    def _reserved_width(drawer: FloatingDrawer, gap: int) -> int:
        return drawer.handle_width + drawer.content_width() + gap


class NetworkConfigDialog(QDialog):
    def __init__(self, project_json_getter=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('网络配置')
        self.resize(760, 560)

        layout = QVBoxLayout(self)
        self.panel = CandidateNetworkPanel(project_json_getter=project_json_getter)
        layout.addWidget(self.panel)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.panel.reload_for_project()


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_project_json_path = None

        # ── load theme BEFORE creating any widgets ──
        self._apply_visual_theme()

        self.setWindowTitle('GMP Generator Engine - UI')
        self.resize(1440, 760)
        self.setMinimumSize(1080, 620)
        
        icon_path = os.path.join(os.path.dirname(__file__), '..', 'icon.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # Top toolbar (horizontal)
        toolbar = QWidget()
        toolbar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(4, 4, 4, 4)
        toolbar_layout.setSpacing(6)

        file_menu = QMenu('文件', self)
        self.action_new = QAction('新建', self)
        self.action_save = QAction('保存', self)
        self.action_load = QAction('读取', self)
        self.action_settings = QAction('设置', self)
        self.action_network_config = QAction('网络配置', self)
        self.action_network_config.setEnabled(False)
        file_menu.addAction(self.action_new)
        file_menu.addAction(self.action_save)
        file_menu.addAction(self.action_load)
        file_menu.addAction(self.action_settings)
        file_menu.addAction(self.action_network_config)
        self.action_new.triggered.connect(self.open_new_project_dialog)
        self.action_load.triggered.connect(self.open_project_json)
        self.action_save.triggered.connect(self.save_project_json)
        self.action_settings.triggered.connect(self.open_settings_dialog)
        self.action_network_config.triggered.connect(self.open_network_config_dialog)

        file_button = QPushButton('文件')
        file_button.setMenu(file_menu)
        file_button.setStyleSheet(
            f'QPushButton {{ border: none; background: transparent; padding: 2px 10px; font-size: 11pt; color: {current_theme().text}; }}'
            'QPushButton::menu-indicator { image: none; width: 0px; }'
            f'QPushButton:hover {{ background: {current_theme().panel_hover}; }}'
        )
        toolbar_layout.addWidget(file_button)

        self.run_agent_button = QPushButton('运行调优')
        self.run_agent_button.setObjectName('primaryButton')
        self.run_agent_button.setStyleSheet(primary_button_qss(padding='6px 16px'))
        self.run_agent_button.clicked.connect(self.run_agent_optimization)
        toolbar_layout.addWidget(self.run_agent_button)

        toolbar_layout.addStretch()
        toolbar.setFixedHeight(36)

        # Central area: AI chat is the base canvas; history and result panels
        # float above it as animated off-canvas drawers.

        self.controller_panel = ControllerStructurePanel(project_json_getter=self.get_current_project_json_path)
        self.tuning_result_panel = TuningResultPanel(project_json_getter=self.get_current_project_json_path)
        self.tuning_result_panel.setStyleSheet(f'background:{current_theme().panel};border:none;')

        self.result_charts_panel = ResultChartsPanel(
            project_json_getter=self.get_current_project_json_path,
        )

        self.right_panel_widget = Design3RightPanel(
            project_json_getter=self.get_current_project_json_path,
            run_tuning_callback=self.run_agent_optimization,
        )
        self.right_panel_widget.setStyleSheet(f'background:{current_theme().surface};border:none;')
        self.right_panel_widget.set_controller_panel(self.controller_panel)
        self.right_panel_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.right_panel_widget.setMinimumWidth(0)

        t = current_theme()
        right_tabs = QTabWidget()
        right_tabs.setStyleSheet(
            f'QTabWidget::pane{{'
            f'  background:{t.panel};'
            f'  border:1px solid {t.border};'
            f'  border-radius:0 0 6px 6px;'
            f'  border-top:none;'
            f'  top:-1px;'
            f'}}'
            f'QTabBar{{'
            f'  background:{t.panel};'
            f'  border:none;'
            f'}}'
            f'QTabBar::tab{{'
            f'  background:{t.tab_bg};'
            f'  color:{t.muted};'
            f'  border:1px solid {t.border};'
            f'  border-bottom:none;'
            f'  border-top-left-radius:6px;'
            f'  border-top-right-radius:6px;'
            f'  min-width:72px;'
            f'  padding:5px 14px;'
            f'  margin-right:2px;'
            f'  margin-bottom:0;'
            f'}}'
            f'QTabBar::tab:selected{{'
            f'  background:{t.panel};'
            f'  color:{t.primary};'
            f'  font-weight:600;'
            f'  border-bottom:1px solid {t.panel};'
            f'}}'
            f'QTabBar::tab:hover:!selected{{'
            f'  background:{t.panel_hover};'
            f'  color:{t.text};'
            f'}}'
        )
        right_tabs.addTab(self.tuning_result_panel, '调优结果')
        right_tabs.addTab(self.result_charts_panel, '仿真图表')
        right_tabs.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        right_tabs.setMinimumWidth(0)

        self.history_panel = HistoryPanel(
            on_project_selected=self._on_history_project_selected,
            on_project_opened=self._on_history_project_opened,
        )
        self.history_panel.setMinimumWidth(200)

        central = OverlayWorkspace(
            center_widget=self.right_panel_widget,
            left_widget=self.history_panel,
            right_widget=right_tabs,
        )
        self.overlay_workspace = central
        central.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Assemble main layout
        main_layout.addWidget(toolbar)
        main_layout.addWidget(central, 1)

        self.setCentralWidget(container)
        self._install_surface_effects()
        self.history_panel.refresh()

    def _apply_visual_theme(self):
        theme = 'light'
        try:
            settings = load_settings()
            ui_cfg = settings.get('ui') if isinstance(settings.get('ui'), dict) else {}
            theme = str(ui_cfg.get('theme', 'light')).lower()
        except Exception:
            pass

        if theme == 'dark':
            self.setStyleSheet(dark_qss())
        else:
            self.setStyleSheet(app_qss())

    def _install_surface_effects(self):
        for widget in [self.right_panel()]:
            if widget is not None:
                widget.setGraphicsEffect(None)

    def right_panel(self):
        return getattr(self, 'right_panel_widget', None)

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        if dialog.exec_() == SettingsDialog.Accepted:
            self._apply_visual_theme()

    def open_network_config_dialog(self):
        if not self.current_project_json_path:
            QMessageBox.warning(self, '提示', '请先新建或读取项目 JSON。')
            return
        dialog = NetworkConfigDialog(project_json_getter=self.get_current_project_json_path, parent=self)
        dialog.exec_()

    def open_new_project_dialog(self):
        dialog = NewProjectDialog(self)
        if dialog.exec_() == QDialog.Accepted and dialog.project_json_path:
            self.current_project_json_path = Path(dialog.project_json_path)
            self.action_network_config.setEnabled(True)
            QMessageBox.information(self, '已加载项目', f'当前项目：{self.current_project_json_path}')
            self._refresh_project_panels()
            self._load_panel_data()
            add_to_history(self.current_project_json_path)
            self.history_panel.refresh()

    def get_current_project_json_path(self):
        return self.current_project_json_path

    def _launch_background_script(self, command, *, cwd: Path | None, log_name: str):
        project_json_path = self.get_current_project_json_path()
        project_dir = Path(project_json_path).parent if project_json_path else MOTORAI_ROOT
        log_dir = project_dir / 'log' / 'ui'
        log_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = log_dir / f'{log_name}_stdout.txt'
        stderr_path = log_dir / f'{log_name}_stderr.txt'
        stdout_file = open(stdout_path, 'w', encoding='utf-8')
        stderr_file = open(stderr_path, 'w', encoding='utf-8')
        try:
            kwargs = {
                'cwd': str(cwd) if cwd else None,
                'stdout': stdout_file,
                'stderr': stderr_file,
            }
            process = subprocess.Popen(command, **kwargs)
            stdout_file.close()
            stderr_file.close()
        except Exception:
            stdout_file.close()
            stderr_file.close()
            raise

        # Give the subprocess a moment.  If it crashed immediately (e.g. import
        # error), read stderr and show the user what went wrong.
        try:
            process.wait(timeout=1.5)
            if process.returncode != 0:
                error_text = stderr_path.read_text(encoding="utf-8", errors="replace").strip()
                if not error_text:
                    error_text = "(no stderr output)"
                QMessageBox.critical(
                    self,
                    "子进程异常退出",
                    f"进程返回码 {process.returncode} —— 很可能发生了导入错误或配置错误。\n\nstderr:\n{error_text[-4000:]}",
                )
        except subprocess.TimeoutExpired:
            pass  # still running — normal

        return process, stdout_path, stderr_path

    def run_agent_optimization(self, round_number: int = 0):
        project_json_path = self.get_current_project_json_path()
        if not project_json_path:
            QMessageBox.warning(self, '提示', '请先打开或创建一个项目文件')
            return

        try:
            with open(project_json_path, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
        except Exception as exc:
            QMessageBox.warning(self, '提示', f'读取项目文件失败：{exc}')
            return

        try:
            if isinstance(project_data, dict) and project_data.get('workspace_mode') == 'competition':
                runner_script = MOTORAI_ROOT / 'Competition' / 'competition_runner.py'
                if not runner_script.exists():
                    QMessageBox.warning(self, '提示', f'未找到脚本文件：{runner_script}')
                    return
                candidate_count = int(project_data.get('candidate_count') or 4)

                # 使用 QProcess 监控进程完成，支持多轮自动继续
                project_dir = Path(project_json_path).parent
                log_dir = project_dir / 'log' / 'ui'
                log_dir.mkdir(parents=True, exist_ok=True)
                stdout_path = log_dir / 'competition_runner_stdout.txt'
                stderr_path = log_dir / 'competition_runner_stderr.txt'

                # 如果已有调优进程在运行，先终止旧进程
                old_proc = getattr(self, '_competition_process', None)
                if old_proc is not None and old_proc.state() != QProcess.NotRunning:
                    old_proc.kill()
                    old_proc.waitForFinished(3000)

                self._competition_process = QProcess(self)
                self._competition_process.setProcessChannelMode(QProcess.SeparateChannels)
                self._competition_process.setWorkingDirectory(str(MOTORAI_ROOT))

                self._competition_process.setStandardOutputFile(str(stdout_path))
                self._competition_process.setStandardErrorFile(str(stderr_path))
                self._competition_process.finished.connect(
                    lambda exit_code, exit_status:
                        self._on_competition_finished(exit_code, exit_status,
                                                       project_json_path)
                )

                # 确定当前轮次：手动点击永远从 1 开始，自动继续才传具体轮次
                if round_number <= 0:
                    current_round = 1
                else:
                    current_round = round_number

                cmd_args = [
                    str(runner_script),
                    str(project_json_path),
                    '--candidates', str(candidate_count),
                    '--parallel', '2',
                    '--optimize-parallel', '1',
                    '--round', str(current_round),
                    '--force-next-round',
                ]
                if current_round <= 1:
                    cmd_args.append('--skip-generate')

                self._competition_process.start(sys.executable, cmd_args)
                right_panel = self.right_panel()
                if right_panel is not None:
                    try:
                        right_panel.main_program_panel._append_debug(
                            f'第 {current_round} 轮调优已启动（后台运行中）...')
                        right_panel.main_program_panel._set_status_text(
                            f'状态：第 {current_round} 轮调优进行中')
                    except RuntimeError:
                        pass
                # 图表切到运行中占位状态
                if hasattr(self, 'result_charts_panel') and self.result_charts_panel is not None:
                    self.result_charts_panel.show_running(current_round)
                return

            run_agent_script = Path(__file__).parent / 'run_agent.py'
            if not run_agent_script.exists():
                QMessageBox.warning(self, '提示', f'未找到脚本文件：{run_agent_script}')
                return

            _process, stdout_path, stderr_path = self._launch_background_script(
                [sys.executable, str(run_agent_script), str(project_json_path)],
                cwd=run_agent_script.parent,
                log_name='run_agent',
            )
            QMessageBox.information(
                self,
                '已启动',
                f'调优任务已启动。\n标准输出：{stdout_path}\n错误输出：{stderr_path}'
            )
        except Exception as exc:
            QMessageBox.critical(self, '错误', f'启动失败：{type(exc).__name__}: {exc}')

    def _on_competition_finished(self, exit_code, exit_status, project_json_path):
        """所有 candidate 调优完成后，读取结果并自动决定是否继续下一轮。"""
        # 清理进程引用
        proc = getattr(self, '_competition_process', None)
        if proc is not None:
            proc.deleteLater()
            self._competition_process = None

        project_dir = Path(project_json_path).parent

        # 读取最新已完成的轮次反馈
        rounds_root = project_dir / 'rounds'
        current_round = 0
        feedback = {}
        if rounds_root.exists():
            import re
            for d in sorted(rounds_root.glob('round_*'), reverse=True):
                fb = d / 'round_feedback.json'
                if fb.exists():
                    m = re.search(r'round_(\d+)', d.name)
                    if m:
                        current_round = int(m.group(1))
                    try:
                        with open(fb, 'r', encoding='utf-8') as f:
                            feedback = json.load(f)
                    except Exception:
                        pass
                    break
        if current_round <= 0:
            current_round = 1

        winner = feedback.get('winner', {})
        scoreboard = feedback.get('scoreboard', [])
        satisfied = feedback.get('requirement_satisfied', False)

        lines = [f'第 {current_round} 轮调优已完成。']
        if winner:
            lines.append(f'最高分：{_short_id(winner["candidate_id"])}（{winner["overall_score"]} 分）')
        if scoreboard:
            lines.append('各组得分：')
            for item in scoreboard:
                lines.append(f'  - {_short_id(item["candidate_id"])}：{item["overall_score"]} 分')

        if exit_code != 0:
            lines.append(f'进程异常退出（返回码 {exit_code}）')
        elif satisfied:
            lines.append('停止条件已满足，迭代结束。')

        message = '\n'.join(lines)

        try:
            right_panel = self.right_panel()
            if right_panel is not None:
                right_panel.main_program_panel._append_notice(message)
                right_panel.main_program_panel._set_status_text(
                    f'状态：第 {current_round} 轮完成（条件已满足）' if satisfied
                    else f'状态：第 {current_round} 轮完成'
                )
        except RuntimeError:
            return

        # 每轮结束后刷新图表
        if hasattr(self, 'result_charts_panel') and self.result_charts_panel is not None:
            try:
                self.result_charts_panel.reload_for_project()
            except Exception:
                pass

        # 检查 max_rounds 上限
        try:
            with open(project_json_path, 'r', encoding='utf-8') as f:
                max_rounds = json.load(f).get('max_rounds', 0)
        except Exception:
            max_rounds = 0

        if not satisfied and exit_code == 0 and (max_rounds <= 0 or current_round < max_rounds):
            try:
                right_panel.main_program_panel._append_notice(
                    f'正在自动启动第 {current_round + 1} 轮仿真...'
                )
            except RuntimeError:
                return
            QTimer.singleShot(500, lambda: self._start_next_round(current_round + 1))
        elif max_rounds > 0 and current_round >= max_rounds and not satisfied:
            try:
                right_panel.main_program_panel._append_notice(
                    f'已达到最大轮次上限（{max_rounds}），停止迭代。'
                )
            except RuntimeError:
                pass

    def _start_next_round(self, next_round: int):
        """生成下一轮策略并自动启动调优。"""
        project_json_path = self.get_current_project_json_path()
        if not project_json_path:
            return
        project_dir = Path(project_json_path).parent
        next_profiles = project_dir / 'rounds' / f'round_{next_round:02d}' / 'candidate_profiles.json'
        right_panel = self.right_panel()

        # 如果策略文件不存在，先生成
        if not next_profiles.exists():
            try:
                if right_panel is not None:
                    right_panel.main_program_panel._append_debug(
                        f'正在生成第 {next_round} 轮方案策略（需要调用 LLM）...'
                    )
                from Competition.next_round_strategy import generate_next_round_strategy
                generate_next_round_strategy(project_json_path,
                                             from_round=next_round - 1,
                                             to_round=next_round)
            except Exception as exc:
                if right_panel is not None:
                    right_panel.main_program_panel._append_error(
                        f'无法生成第 {next_round} 轮策略：{exc}')
                return

        # 直接启动，不弹窗
        self.run_agent_optimization(round_number=next_round)

    def _read_project_open_root(self):
        return str(get_output_root(load_settings()))

    def open_project_json(self):
        default_dir = self._read_project_open_root()
        file_path, _ = QFileDialog.getOpenFileName(self, '选择项目 JSON 文件', default_dir, 'JSON Files (*.json)')
        if not file_path:
            return
        selected = Path(file_path)
        try:
            with open(selected, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError('JSON 顶层必须是对象')
            self.current_project_json_path = selected
            self.action_network_config.setEnabled(True)
            QMessageBox.information(self, '已加载项目', f'当前项目：{self.current_project_json_path}')
            self._refresh_project_panels()
            self._load_panel_data()
            add_to_history(self.current_project_json_path)
            self.history_panel.refresh()
        except Exception as exc:
            QMessageBox.critical(self, '错误', f'加载项目 JSON 失败：{exc}')

    def _on_history_project_selected(self, json_path: Path) -> None:
        """Single-click on a history item: info is shown by the panel itself."""
        pass

    def _on_history_project_opened(self, json_path: Path) -> None:
        """Double-click on a history item: load the project."""
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("JSON 顶层必须是对象")
            self.current_project_json_path = json_path
            self.action_network_config.setEnabled(True)
            self._refresh_project_panels()
            self._load_panel_data()
            add_to_history(json_path)
            self.history_panel.refresh()
        except Exception as exc:
            QMessageBox.critical(self, '错误', f'加载项目 JSON 失败：{exc}')

    def _refresh_project_panels(self):
        if hasattr(self, 'left_controller_panel') and self.controller_panel is not None:
            self.controller_panel.refresh_from_project()
        if hasattr(self, 'tuning_result_panel') and self.tuning_result_panel is not None:
            self.tuning_result_panel.refresh_from_project()

    def _load_panel_data(self):
        right_panel = self.right_panel()
        if not right_panel:
            return

        widgets = right_panel.project_widgets() if hasattr(right_panel, 'project_widgets') else []
        for widget in widgets:
            if hasattr(widget, 'reload_for_project'):
                widget.reload_for_project()
            elif hasattr(widget, '_load_chat_record'):
                widget._load_chat_record()
            if hasattr(widget, 'load_from_csv'):
                widget.load_from_csv()
            if hasattr(widget, 'load_from_project_json'):
                try:
                    widget.load_from_project_json()
                except Exception:
                    pass

        # 刷新仿真结果图表
        if hasattr(self, 'result_charts_panel') and self.result_charts_panel is not None:
            self.result_charts_panel.reload_for_project()

    def save_project_json(self):
        if not self.current_project_json_path:
            QMessageBox.warning(self, '提示', '请先新建或读取项目 JSON。')
            return
        try:
            with open(self.current_project_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            with open(self.current_project_json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, '完成', f'已保存：{self.current_project_json_path}')
        except Exception as exc:
            QMessageBox.critical(self, '错误', f'保存项目 JSON 失败：{exc}')
