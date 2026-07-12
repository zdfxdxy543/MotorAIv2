from PyQt5.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
    QVBoxLayout,
)
from PyQt5.QtCore import Qt, QDateTime, QSize, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QMovie
import json
from pathlib import Path

from core.paths import GENERATE_ROOT, MOTORAI_ROOT
from styles.theme import (
    RADIUS_CARD,
    current_theme,
    flat_button_qss,
    ghost_button_qss,
    primary_button_qss,
    secondary_button_qss,
    surface_card_qss,
)
from widgets.chat import ChatInputEdit, ChatStreamWidget, ChatWorker, call_ui_chat_model
from workflow.agent_flow import (
    ACTION_ANSWER_QUESTION,
    ACTION_CLARIFY,
    ACTION_CONFIRM_GENERATE,
    ACTION_CONTINUE_NEXT_ROUND,
    ACTION_REVISE_PROGRAM,
    ACTION_SHOW_LOAD_CURVE,
    ACTION_START_TUNING,
    ACTION_SUBMIT_METRICS,
    FlowRouteWorker,
    heuristic_route,
)
import controller_loop_id_exporter as loop_exporter
import merge_loop_ids_into_ctl_main as merger
from Competition.competition_workspace import (
    apply_candidate_profile_overrides,
    build_candidate_generation_requirement,
    candidate_design_profile,
    candidate_llm_temperature,
    configure_candidate_optimize,
    discover_candidate_dirs,
    sync_candidate_profiles_from_common,
    write_candidate_generation_context,
    write_common_requirement_snapshot,
)


WELCOME_GIF_SIZE = 50
INPUT_CARD_RADIUS = 16
WELCOME_INPUT_MAX_WIDTH = 1020
CHAT_INPUT_MAX_WIDTH = 1020


def _build_tuning_policy_from_loops(selected_loops):
    loop_names = {loop.get('name', '').lower() for loop in selected_loops if isinstance(loop, dict)}

    allowed_parameters = {}
    if 'current_loop' in loop_names or 'current_error_loop' in loop_names:
        allowed_parameters['CUR_KP'] = {'min': 1.0, 'max': 500.0, 'description': '电流环比例增益'}
        allowed_parameters['CUR_KI'] = {'min': 0.0, 'max': 12000.0, 'description': '电流环积分增益'}
        allowed_parameters['CUR_LIMIT'] = {'min': 0.05, 'max': 10.0, 'description': '电流限幅'}
    if 'speed_loop' in loop_names or 'speed_error_loop' in loop_names or 'mech_loop' in loop_names:
        allowed_parameters['VEL_KP'] = {'min': 0.1, 'max': 20.0, 'description': '速度环比例增益'}
        allowed_parameters['VEL_KI'] = {'min': 0.0, 'max': 5.0, 'description': '速度环积分增益'}
        allowed_parameters['CUR_LIMIT'] = {'min': 0.05, 'max': 10.0, 'description': '电流限幅'}
    if 'position_loop' in loop_names or 'position_error_loop' in loop_names:
        allowed_parameters['POS_KP'] = {'min': 0.1, 'max': 50.0, 'description': '位置环比例增益'}
        allowed_parameters['POS_KI'] = {'min': 0.0, 'max': 10.0, 'description': '位置环积分增益'}
        allowed_parameters['VEL_LIMIT'] = {'min': 0.1, 'max': 100.0, 'description': '速度限幅'}
    if 'torque_loop' in loop_names or 'torque_reference_loop' in loop_names:
        allowed_parameters['TRQ_KP'] = {'min': 1.0, 'max': 500.0, 'description': '转矩环比例增益'}
        allowed_parameters['TRQ_KI'] = {'min': 0.0, 'max': 100.0, 'description': '转矩环积分增益'}

    return {
        'allowed_parameters': allowed_parameters,
        'update_rule': '每轮可同时修改多个参数，数量上限由候选方案激进程度决定；如果编译、仿真或评价失败，不修改参数。'
    }


class GenerateProgramWorker(QThread):
    progress = pyqtSignal(str)
    debug = pyqtSignal(str)
    success = pyqtSignal(dict)
    failure = pyqtSignal(str)

    def __init__(
        self,
        requirement: str,
        project_json: Path,
        candidate_dirs: list[Path],
        template_dir: Path,
        llm_config: Path,
        parent=None,
    ):
        super().__init__(parent)
        self.requirement = requirement
        self.project_json = Path(project_json)
        self.candidate_dirs = [Path(candidate_dir) for candidate_dir in candidate_dirs]
        self.template_dir = Path(template_dir)
        self.llm_config = Path(llm_config)

    def run(self):
        try:
            self.success.emit(self._generate())
        except Exception as exc:
            self.failure.emit(str(exc))

    def _generate(self) -> dict:
        self.progress.emit(f'正在为 {len(self.candidate_dirs)} 个 candidate 生成控制器程序...')
        sync_candidate_profiles_from_common(self.project_json, self.candidate_dirs)
        candidate_summaries = []
        first_loop_ids_path = None
        first_candidate_data = None

        for index, candidate_dir in enumerate(self.candidate_dirs, start=1):
            profile = self._load_candidate_profile(candidate_dir, index)
            loop_ids_output = candidate_dir / 'log' / 'generate' / 'controller_loop_ids_generated.json'
            c_output = candidate_dir / 'src' / 'ctl_main.c'
            h_output = candidate_dir / 'src' / 'ctl_main.h'
            paras_output = candidate_dir / 'src' / 'paras.generated.h'
            loop_ids_output.parent.mkdir(parents=True, exist_ok=True)
            c_output.parent.mkdir(parents=True, exist_ok=True)

            candidate_requirement = build_candidate_generation_requirement(self.requirement, profile)
            write_candidate_generation_context(
                candidate_dir / 'candidate.json',
                self.requirement,
                candidate_requirement,
                profile,
            )
            profile_temperature = candidate_llm_temperature(profile)

            profile_name = profile.get('name', candidate_dir.name)
            self.progress.emit(f'[{index}/{len(self.candidate_dirs)}] 正在生成 {candidate_dir.name} 的 loop-ids...')
            self.debug.emit(f'[{index}/{len(self.candidate_dirs)}] {candidate_dir.name} 生成 loop-ids：{profile_name}')
            loop_exporter.export_json(
                output_path=loop_ids_output,
                requirement=candidate_requirement,
                settings_path=self.llm_config,
                chat_text_caller=lambda system_prompt, user_prompt, temp, temperature=profile_temperature: call_ui_chat_model(
                    user_prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=temperature if temperature is not None else temp,
                ),
                temperature_override=profile_temperature,
            )

            self.progress.emit(f'[{index}/{len(self.candidate_dirs)}] 正在生成 {candidate_dir.name} 的控制程序文件...')
            self.debug.emit(f'[{index}/{len(self.candidate_dirs)}] {candidate_dir.name} 生成 ctl_main 与 paras')
            merge_code = merger.main(
                loop_ids_path=loop_ids_output,
                template_path=self.template_dir / 'ctl_main.c',
                output_path=c_output,
                header_template_path=self.template_dir / 'ctl_main.h',
                header_output_path=h_output,
                paras_template_path=self.template_dir / 'paras.h',
                paras_output_path=paras_output,
            )
            if merge_code != 0:
                raise RuntimeError(f'{candidate_dir.name} 模板合并失败，返回码：{merge_code}')
            for generated_path in (c_output, h_output, paras_output):
                if not generated_path.exists():
                    raise FileNotFoundError(f'{candidate_dir.name} 未生成文件：{generated_path}')

            # ── 复制 user_main.c / user_main.h ─────────────────────────
            for name in ('user_main.c', 'user_main.h'):
                src = self.template_dir / name
                dst = c_output.parent / name
                if src.exists():
                    import shutil
                    shutil.copy2(src, dst)

            # ── Step 0: 差异化参数种子 ─────────────────────────────────
            self._seed_candidate_parameters(paras_output, index, profile,
                                            candidate_dir)

            # ── Step 1: 控制器结构清单 ─────────────────────────────────
            self._write_candidate_manifest(candidate_dir)

            candidate_data = self._write_candidate_generated_result(candidate_dir, loop_ids_output, profile)
            if first_loop_ids_path is None:
                first_loop_ids_path = loop_ids_output
                first_candidate_data = candidate_data

            candidate_summaries.append({
                'candidate_id': candidate_dir.name,
                'design_profile': profile,
                'loop_ids': str(loop_ids_output),
                'ctl_main_c': str(c_output),
                'ctl_main_h': str(h_output),
                'paras_header': str(paras_output),
            })

        if first_loop_ids_path is not None:
            self._update_project_json_selected_loops(first_loop_ids_path)

        with open(self.project_json, 'r', encoding='utf-8') as f:
            project_data = json.load(f)
        if not isinstance(project_data, dict):
            project_data = {}
        project_data['candidate_generation'] = candidate_summaries
        if isinstance(first_candidate_data, dict):
            project_data['selected_loops'] = first_candidate_data.get('selected_loops') or []
            project_data['tuning_policy'] = first_candidate_data.get('tuning_policy') or {}
        with open(self.project_json, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, ensure_ascii=False, indent=2)

        return {
            'candidate_count': len(candidate_summaries),
            'first_loop_ids_path': str(first_loop_ids_path) if first_loop_ids_path is not None else '',
        }

    @staticmethod
    def _load_candidate_profile(candidate_dir: Path, index: int) -> dict:
        profile = candidate_design_profile(index)
        candidate_json = candidate_dir / 'candidate.json'
        if not candidate_json.exists():
            return profile
        try:
            with open(candidate_json, 'r', encoding='utf-8') as f:
                candidate_data = json.load(f)
            candidate_profile = candidate_data.get('design_profile') if isinstance(candidate_data, dict) else None
            if isinstance(candidate_profile, dict):
                merged = dict(profile)
                merged.update(candidate_profile)
                return merged
        except Exception:
            pass
        return profile

    @staticmethod
    def _write_candidate_generated_result(candidate_dir: Path, loop_ids_path: Path, profile: dict):
        with open(loop_ids_path, 'r', encoding='utf-8') as f:
            loops_payload = json.load(f)
        if not isinstance(loops_payload, dict):
            return {}

        candidate_json = candidate_dir / 'candidate.json'
        with open(candidate_json, 'r', encoding='utf-8') as f:
            candidate_data = json.load(f)
        if not isinstance(candidate_data, dict):
            candidate_data = {}

        selected_loops = loops_payload.get('selected_loops') or []
        candidate_data['selected_loops'] = selected_loops
        candidate_data['generated_loop_ids_path'] = str(loop_ids_path)
        candidate_data['design_profile'] = profile
        candidate_data['tuning_policy'] = _build_tuning_policy_from_loops(selected_loops)
        candidate_data.setdefault('paths', {})
        candidate_data['paths']['header_path'] = 'src/paras.generated.h'
        candidate_data['paths']['result_file'] = 'log/optimize/tuning_result.json'
        with open(candidate_json, 'w', encoding='utf-8') as f:
            json.dump(candidate_data, f, ensure_ascii=False, indent=2)

        configure_candidate_optimize(candidate_json)
        return candidate_data

    def _update_project_json_selected_loops(self, loop_ids_path: Path):
        with open(loop_ids_path, 'r', encoding='utf-8') as f:
            loops_payload = json.load(f)
        if not isinstance(loops_payload, dict):
            return

        with open(self.project_json, 'r', encoding='utf-8') as f:
            project_data = json.load(f)
        if not isinstance(project_data, dict):
            project_data = {}

        selected_loops = loops_payload.get('selected_loops') or []
        project_data['selected_loops'] = selected_loops
        project_data['generated_loop_ids_path'] = str(loop_ids_path)
        paths = project_data.get('paths')
        if not isinstance(paths, dict):
            paths = {}
            project_data['paths'] = paths
        paths['generated_loop_ids_path'] = str(loop_ids_path)
        project_data['tuning_policy'] = _build_tuning_policy_from_loops(selected_loops)

        with open(self.project_json, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, ensure_ascii=False, indent=2)
        self.debug.emit('主程序结构已保存到当前项目。')
        self.debug.emit('调参策略已准备好。')

    def _seed_candidate_parameters(self, paras_output, candidate_index, profile, candidate_dir):
        """根据 parameter_seed_policy 为 candidate 设置差异化初始参数值。"""
        try:
            from Competition.parameter_seeder import seed_parameters
            seed_report_dir = candidate_dir / 'log' / 'generate'
            seed_report_dir.mkdir(parents=True, exist_ok=True)
            seed_policy = profile.get('parameter_seed_policy') if isinstance(profile, dict) else None
            if isinstance(seed_policy, dict) and seed_policy.get('mode') in ('inherit', 'inherit_then_perturb'):
                mode = str(seed_policy.get('mode', '') or '').strip()
                source_id = str(seed_policy.get('source_candidate', '') or '').strip()
                if source_id:
                    source_header = candidate_dir.parent / source_id / 'src' / 'paras.generated.h'
                    # 优先从 rounds 备份读取
                    project_root = candidate_dir.parent.parent
                    rounds_dir = project_root / 'rounds'
                    if rounds_dir.is_dir():
                        for rd in sorted(rounds_dir.glob('round_*'), reverse=True):
                            backup = rd / 'candidates' / source_id / 'src' / 'paras.generated.h'
                            if backup.exists():
                                source_header = backup
                                break
                    if source_header.exists():
                        from Optimize.agent_optimize.agent_core.parameters.parameter_header_editor import (
                            read_tunable_parameters_detailed,
                            patch_tunable_parameters,
                        )
                        import re
                        from Competition.parameter_seeder import _FIXED_PARAMETERS
                        target_params = read_tunable_parameters_detailed(paras_output)
                        source_params = read_tunable_parameters_detailed(source_header)
                        inherited = {}
                        for name in target_params:
                            if name in source_params and name.upper().strip() not in _FIXED_PARAMETERS:
                                inherited[name] = source_params[name].value
                        if mode == 'inherit_then_perturb':
                            perturbation_text = str(seed_policy.get('perturbation_direction', '') or '').strip()
                            if perturbation_text:
                                _PT_DIR = r'(提高|增加|加大|升高|上调|降低|减少|减小|下调)'
                                _PT_NAME_LIST = r'([A-Za-z_][A-Za-z0-9_]*(?:\s*(?:和|、|,)\s*[A-Za-z_][A-Za-z0-9_]*)*)'
                                _PT_PCT = r'(?:约|約|大约|大概)?\s*(\d+(?:\.\d+)?)\s*%'
                                _PT_FILLER = r'(?:再|进一步|适当|略微|小幅|大幅)?\s*'

                                def _apply_pert(dir_word, names_text, pct_val):
                                    for rn in re.split(r'\s*(?:和|、|,)\s*', names_text):
                                        pn = rn.strip().upper()
                                        if not pn or pn not in inherited:
                                            continue
                                        if dir_word in ('提高', '增加', '加大', '升高', '上调'):
                                            inherited[pn] = round(inherited[pn] * (1.0 + pct_val), 6)
                                        else:
                                            inherited[pn] = round(inherited[pn] * (1.0 - pct_val), 6)

                                # 语序 A：方向词在前
                                for match in re.finditer(
                                    rf'{_PT_DIR}\s*{_PT_FILLER}?{_PT_NAME_LIST}\s*{_PT_PCT}',
                                    perturbation_text,
                                ):
                                    _apply_pert(match.group(1), match.group(2), float(match.group(3)) / 100.0)
                                # 语序 B：参数名在前
                                for match in re.finditer(
                                    rf'{_PT_NAME_LIST}\s*{_PT_FILLER}{_PT_DIR}\s*{_PT_PCT}',
                                    perturbation_text,
                                ):
                                    _apply_pert(match.group(2), match.group(1), float(match.group(3)) / 100.0)
                        if inherited:
                            patch_tunable_parameters(paras_output, inherited, backup=True)
                            self.debug.emit(f'  [seed] {candidate_dir.name}: 从 {source_id} 继承 {len(inherited)} 个参数 (mode={mode})')
                            return
            # fallback: 使用差异化乘性扰动
            report = seed_parameters(
                paras_output,
                candidate_index=candidate_index,
                profile=profile,
                seed_report_dir=seed_report_dir,
                label=candidate_dir.name,
            )
            self.debug.emit(f'  [seed] {candidate_dir.name}: {report.get("updated_count", 0)} updated, {report.get("skipped_count", 0)} skipped')
        except Exception as exc:
            self.debug.emit(f'  [seed] warning: parameter seeding failed ({exc}), keeping defaults')

    def _write_candidate_manifest(self, candidate_dir):
        """生成控制器结构清单。"""
        try:
            from Competition.controller_manifest import write_controller_manifest
            manifest_path = write_controller_manifest(candidate_dir)
            self.debug.emit(f'  [manifest] wrote {manifest_path.name}')
        except Exception as exc:
            self.debug.emit(f'  [manifest] warning: controller manifest failed ({exc})')


def _apply_floating_input_shadow(widget: QWidget):
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(22)
    shadow.setOffset(0, 8)
    shadow.setColor(QColor(15, 23, 42, 36))
    widget.setGraphicsEffect(shadow)


def _floating_input_card_qss(object_name: str) -> str:
    t = current_theme()
    return (
        f'QFrame#{object_name}{{background:{t.surface};border:1px solid {t.border};'
        f'border-radius:{INPUT_CARD_RADIUS}px;}}'
        f'QFrame#{object_name}:hover{{border-color:{t.border_strong};}}'
        f'QFrame#{object_name} QTextEdit,'
        f'QFrame#{object_name} QLineEdit{{background:transparent;border:none;color:{t.text};}}'
    )


class IntentConfirmCard(QFrame):
    def __init__(
        self,
        intent_title: str,
        summary: str,
        confirm_label: str,
        alternative_label: str,
        on_confirm,
        on_alternative,
        on_cancel,
        parent=None,
    ):
        super().__init__(parent)
        self._resolved = False
        self._on_confirm = on_confirm
        self._on_alternative = on_alternative
        self._on_cancel = on_cancel
        self.setObjectName('intentConfirmCard')
        self.setStyleSheet(surface_card_qss('intentConfirmCard'))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title_label = QLabel(f'我理解你想：{intent_title}')
        title_label.setStyleSheet(f'font-size:13pt;font-weight:700;color:{current_theme().text_strong};')
        layout.addWidget(title_label)

        summary_label = QLabel(f'内容摘要：{summary}')
        summary_label.setWordWrap(True)
        summary_label.setStyleSheet(f'color:{current_theme().muted};line-height:1.45;')
        layout.addWidget(summary_label)

        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 2, 0, 0)
        button_layout.setSpacing(8)
        button_layout.addStretch()

        self.confirm_btn = QPushButton(confirm_label)
        self.confirm_btn.setObjectName('primaryButton')
        self.confirm_btn.setStyleSheet(primary_button_qss())
        self.alternative_btn = QPushButton(alternative_label)
        self.alternative_btn.setObjectName('secondaryActionButton')
        self.alternative_btn.setStyleSheet(secondary_button_qss())
        if not alternative_label:
            self.alternative_btn.hide()
        self.cancel_btn = QPushButton('取消')
        self.cancel_btn.setObjectName('ghostButton')
        self.cancel_btn.setStyleSheet(ghost_button_qss())

        self.confirm_btn.clicked.connect(lambda: self._resolve(self._on_confirm))
        if alternative_label:
            self.alternative_btn.clicked.connect(lambda: self._resolve(self._on_alternative))
        self.cancel_btn.clicked.connect(lambda: self._resolve(self._on_cancel))

        button_layout.addWidget(self.confirm_btn)
        if alternative_label:
            button_layout.addWidget(self.alternative_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addWidget(button_row)

    def _resolve(self, callback):
        if self._resolved:
            return
        self._resolved = True
        for button in (self.confirm_btn, self.alternative_btn, self.cancel_btn):
            button.setEnabled(False)
        if callable(callback):
            callback()


class MainProgramPanel(QWidget):
    def __init__(self, project_json_getter=None, structure_refresh_callback=None, parent=None):
        super().__init__(parent)
        self.current_requirement = ''
        self.chat_worker = None
        self.route_worker = None
        self.program_worker = None
        self._chat_task = None
        self._pending_route_text = ''
        self._pending_program_text = ''
        self._program_requirement_before_refine = ''
        self.project_json_getter = project_json_getter
        self.structure_refresh_callback = structure_refresh_callback
        self.chat_history = []
        self.load_curve_panel = None
        self.requirement_panel = None
        self.run_tuning_callback = None
        self.input_mode = 'agent'
        self._workflow_steps = set()
        self._main_content_widgets = []
        self._load_curve_card_count = 0
        self._auto_tuning_started = False
        self._auto_tuning_confirm_pending = False
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)

        self.chat_view = ChatStreamWidget()
        
        self.input_dock = QWidget()
        self.input_dock.setObjectName('floatingInputDock')
        self.input_dock.setAttribute(Qt.WA_StyledBackground, True)
        self.input_dock.setStyleSheet('QWidget#floatingInputDock{background:transparent;border:none;}')
        input_dock_layout = QHBoxLayout(self.input_dock)
        input_dock_layout.setContentsMargins(0, 4, 0, 10)
        input_dock_layout.setSpacing(0)
        input_dock_layout.addStretch(1)

        self.input_row = QFrame()
        self.input_row.setObjectName('floatingInputCard')
        self.input_row.setAttribute(Qt.WA_StyledBackground, True)
        self.input_row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.input_row.setStyleSheet(_floating_input_card_qss('floatingInputCard'))
        _apply_floating_input_shadow(self.input_row)
        input_layout = QHBoxLayout(self.input_row)
        input_layout.setContentsMargins(14, 8, 12, 8)
        input_layout.setSpacing(10)

        self.input_edit = ChatInputEdit()
        self.input_edit.setPlaceholderText('有需求，尽管说')
        self.input_edit.setFixedHeight(66)
        self.input_edit.setStyleSheet(f'''
            QTextEdit {{
                background: transparent;
                border: none;
                border-radius: 0px;
                padding: 8px 10px;
                font-size: 11pt;
                color: {current_theme().text};
            }}
            QTextEdit:focus {{
                border: none;
                outline: none;
            }}
        ''')
        self.input_edit.enterPressed.connect(self.send_requirement)

        input_actions = QWidget()
        input_actions_layout = QVBoxLayout(input_actions)
        input_actions_layout.setContentsMargins(0, 0, 0, 0)
        input_actions_layout.setSpacing(8)
        self.send_btn = QPushButton('发送需求')
        self.send_btn.setObjectName('primaryButton')
        self.send_btn.setStyleSheet(primary_button_qss(padding='7px 14px'))
        self.send_btn.clicked.connect(self.send_requirement)
        input_actions_layout.addWidget(self.send_btn)
        input_actions_layout.addStretch()

        input_layout.addWidget(self.input_edit, 1)
        input_layout.addWidget(input_actions)
        input_dock_layout.addWidget(self.input_row, 0, Qt.AlignCenter)
        input_dock_layout.addStretch(1)

        self.action_row = QWidget()
        action_layout = QHBoxLayout(self.action_row)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)
        action_layout.addStretch()
        self.run_btn = QPushButton('生成程序')
        self.run_btn.setObjectName('secondaryActionButton')
        self.run_btn.clicked.connect(self.generate_program)
        action_layout.addWidget(self.run_btn)

        self._status_text = '状态：等待输入需求'

        self.welcome_overlay = QWidget()
        self.welcome_layout = QVBoxLayout(self.welcome_overlay)
        self.welcome_layout.setContentsMargins(0, 0, 0, 0)
        self.welcome_layout.setSpacing(0)
        
        self.welcome_prompt_row = QWidget()
        self.welcome_prompt_row.setStyleSheet('border: none; background: transparent;')
        welcome_prompt_layout = QHBoxLayout(self.welcome_prompt_row)
        welcome_prompt_layout.setContentsMargins(0, 0, 0, 14)
        welcome_prompt_layout.setSpacing(10)

        self.welcome_gif_label = QLabel()
        self.welcome_gif_label.setFixedSize(WELCOME_GIF_SIZE, WELCOME_GIF_SIZE)
        self.welcome_gif_label.setAlignment(Qt.AlignCenter)
        self.welcome_gif_label.setFrameShape(QFrame.NoFrame)
        self.welcome_gif_label.setStyleSheet('border: none; outline: none; margin: 0; padding: 0;')
        self.welcome_movie = None
        welcome_gif_path = GENERATE_ROOT / '旋转.gif'
        if welcome_gif_path.exists():
            self.welcome_movie = QMovie(str(welcome_gif_path))
            self.welcome_movie.setScaledSize(QSize(WELCOME_GIF_SIZE, WELCOME_GIF_SIZE))
            self.welcome_gif_label.setMovie(self.welcome_movie)
            self.welcome_movie.start()

        self.welcome_prompt_label = QLabel('想生成什么电机程序？')
        self.welcome_prompt_label.setStyleSheet(f'''
            QLabel {{
                font-size: 18pt;
                font-weight: 700;
                color: {current_theme().text};
                border: none;
                background: transparent;
            }}
        ''')
        welcome_prompt_layout.addWidget(self.welcome_gif_label)
        welcome_prompt_layout.addWidget(self.welcome_prompt_label)

        self.welcome_input_shell = QFrame()
        self.welcome_input_shell.setObjectName('welcomeInputCard')
        self.welcome_input_shell.setAttribute(Qt.WA_StyledBackground, True)
        self.welcome_input_shell.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.welcome_input_shell.setStyleSheet(_floating_input_card_qss('welcomeInputCard'))
        _apply_floating_input_shadow(self.welcome_input_shell)
        welcome_input_layout = QHBoxLayout(self.welcome_input_shell)
        welcome_input_layout.setContentsMargins(20, 8, 20, 8)
        welcome_input_layout.setSpacing(0)

        self.welcome_input = QLineEdit()
        self.welcome_input.setPlaceholderText('有需求，尽管说')
        self.welcome_input.setStyleSheet(f'''
            QLineEdit {{
                background: transparent;
                border: none;
                border-radius: 0px;
                padding: 10px 6px;
                font-size: 14pt;
                color: {current_theme().text};
                min-height: 46px;
            }}
            QLineEdit::placeholder {{
                color: {current_theme().muted};
            }}
        ''')
        self.welcome_input.returnPressed.connect(self._on_welcome_input)
        welcome_input_layout.addWidget(self.welcome_input)
        
        self.quick_action_buttons = QWidget()
        self.quick_action_buttons.setStyleSheet('border: none; background: transparent;')
        quick_action_layout = QHBoxLayout(self.quick_action_buttons)
        quick_action_layout.setContentsMargins(0, 20, 0, 0)
        quick_action_layout.setSpacing(16)
        
        self.btn_vacuum = QPushButton('设计PID转速控制')
        self.btn_vacuum.setStyleSheet(flat_button_qss() + 'QPushButton{min-width:160px;}')
        self.btn_vacuum.setFlat(True)
        self.btn_vacuum.clicked.connect(lambda: self._apply_quick_template('PID转速控制'))
        
        self.btn_servo = QPushButton('设计LADRC转速控制')
        self.btn_servo.setStyleSheet(flat_button_qss() + 'QPushButton{min-width:180px;}')
        self.btn_servo.setFlat(True)
        self.btn_servo.clicked.connect(lambda: self._apply_quick_template('LADRC转速控制'))
        
        self.btn_current = QPushButton('设计位置伺服控制')
        self.btn_current.setStyleSheet(flat_button_qss() + 'QPushButton{min-width:160px;}')
        self.btn_current.setFlat(True)
        self.btn_current.clicked.connect(lambda: self._apply_quick_template('位置伺服控制'))
        
        quick_action_layout.addWidget(self.btn_vacuum)
        quick_action_layout.addWidget(self.btn_servo)
        quick_action_layout.addWidget(self.btn_current)
        
        self.welcome_layout.addStretch(7)
        self.welcome_layout.addWidget(self.welcome_prompt_row, 0, Qt.AlignCenter)
        self.welcome_layout.addWidget(self.welcome_input_shell, 0, Qt.AlignCenter)
        self.welcome_layout.addWidget(self.quick_action_buttons, 0, Qt.AlignCenter)
        self.welcome_layout.addStretch(4)
        self.welcome_overlay.setStyleSheet(f'background:{current_theme().surface};')
        
        self._load_chat_record()
        
        if not self.chat_history:
            self.show_welcome_overlay()
        else:
            self.show_main_content()
        self._sync_input_widths()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_input_widths()

    def _sync_input_widths(self):
        available = max(320, self.width())
        welcome_width = min(WELCOME_INPUT_MAX_WIDTH, available)
        chat_width = min(CHAT_INPUT_MAX_WIDTH, available)

        if hasattr(self, 'welcome_input_shell'):
            self.welcome_input_shell.setFixedWidth(welcome_width)
        if hasattr(self, 'input_row'):
            self.input_row.setFixedWidth(chat_width)

    def show_welcome_overlay(self):
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
        self._main_content_widgets = []
        self._set_program_input_mode()
        
        self.welcome_overlay.show()
        self.main_layout.addWidget(self.welcome_overlay)
        self._sync_input_widths()
    
    def show_main_content(self):
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()

        self._main_content_widgets = [
            self.chat_view,
            self.input_dock,
        ]
        self.main_layout.addWidget(self.chat_view, 1)
        self.main_layout.addWidget(self.input_dock)
        
        self.chat_view.show()
        self.input_dock.show()
        self.action_row.hide()
        self._sync_input_widths()

    def _welcome_is_active(self):
        for index in range(self.main_layout.count()):
            item = self.main_layout.itemAt(index)
            if item and item.widget() is self.welcome_overlay:
                return True
        return False

    def set_workflow_widgets(self, load_curve_panel=None, requirement_panel=None, run_tuning_callback=None):
        self.load_curve_panel = load_curve_panel
        self.requirement_panel = requirement_panel
        self.run_tuning_callback = run_tuning_callback

        if self.load_curve_panel is not None:
            self.load_curve_panel.setMinimumHeight(520)
            if hasattr(self.load_curve_panel, 'set_save_callback'):
                self.load_curve_panel.set_save_callback(self._on_load_curve_saved)

        if self.requirement_panel is not None:
            if hasattr(self.requirement_panel, 'set_completion_callback'):
                self.requirement_panel.set_completion_callback(self._on_requirement_ready)
            if hasattr(self.requirement_panel, 'set_external_callbacks'):
                self.requirement_panel.set_external_callbacks(
                    chat_callback=self._append_chat,
                    status_callback=self._set_status_text,
                    finished_callback=self._on_metric_requirement_finished,
                )

        if self.chat_history and not self._welcome_is_active():
            self._restore_workflow_from_project()

    def _make_flow_card(self, title: str, subtitle: str, body_widget: QWidget | None = None) -> QFrame:
        card = QFrame()
        card.setObjectName('workflowCard')
        card.setStyleSheet(surface_card_qss('workflowCard'))
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setStyleSheet(f'font-size:13pt;font-weight:700;color:{current_theme().text_strong};')
        subtitle_label = QLabel(subtitle)
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet(f'color:{current_theme().muted};')
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)

        if body_widget is not None:
            layout.addWidget(body_widget)
            body_widget.setVisible(True)

        return card

    def _append_workflow_widget(self, key: str, widget: QWidget, width_ratio: float = 0.94):
        if key in self._workflow_steps:
            return
        self._workflow_steps.add(key)
        if self._welcome_is_active():
            self.show_main_content()
        self.chat_view.append_widget(widget, width_ratio=width_ratio)

    def show_load_curve_card(self, announce: bool = True, force: bool = False):
        if self.load_curve_panel is None:
            return
        if 'load_curve' in self._workflow_steps and not force:
            return
        if announce:
            self._append_chat('assistant', '请在下方设置负载曲线。保存后可以继续输入指标，也可以随时要求重画。')
        card = self._make_flow_card(
            '负载曲线设置',
            '输入转速和转矩点，保存后会同步到 common/load.csv 和各 candidate 仿真目录。',
            self.load_curve_panel,
        )
        if 'load_curve' not in self._workflow_steps:
            key = 'load_curve'
        else:
            self._load_curve_card_count += 1
            key = f'load_curve_{self._load_curve_card_count}'
        self._append_workflow_widget(key, card)

    def show_tuning_entry_card(self, announce: bool = True):
        self._auto_start_tuning_if_ready(force=False, announce=announce)

    def _on_load_curve_saved(self):
        self._append_success('负载曲线已保存。请在下方输入详细的指标需求；如果还想重画负载曲线，也可以直接告诉我。')
        self._set_metric_input_mode()
        if self._has_metrics_ready():
            self._auto_start_tuning_if_ready(force=True)

    def _on_requirement_ready(self):
        self._auto_start_tuning_if_ready(force=False)

    def _set_status_text(self, text: str):
        self._status_text = text

    def _set_program_input_mode(self):
        self.input_mode = 'agent'
        self.input_edit.setPlaceholderText('可以继续补充需求；确认方案后回复“生成程序”。')
        self.send_btn.setText('发送')
        self.run_btn.setEnabled(False)
        self._set_status_text('状态：等待输入')

    def _set_metric_input_mode(self):
        self.input_mode = 'agent'
        self.input_edit.setPlaceholderText('请输入指标需求；也可以要求重画负载曲线、补充程序需求或继续提问。')
        self.send_btn.setText('发送')
        self.run_btn.setEnabled(False)
        self._set_status_text('状态：等待输入需求指标')

    def _on_metric_requirement_finished(self):
        self.chat_view.hide_thinking()
        self.send_btn.setEnabled(True)

    def _run_tuning_from_chat(self):
        self._set_progress('正在启动调优任务...')
        if callable(self.run_tuning_callback):
            self.run_tuning_callback()

    def _detach_workflow_panels(self):
        for panel in (self.load_curve_panel, self.requirement_panel):
            if panel is not None:
                panel.hide()
                panel.setParent(None)

    def _program_requirement_prompt(self):
        return (
            '你是面向 loop-ids 生成系统的控制器需求完善助手。'
            '你的任务是把用户原始需求改写为可直接用于控制环路选择与程序生成的中文需求。'
            '控制结构、环路层级、控制方法、PWM 调制策略和候选方案侧重是 MotorAI 需要根据需求推断和设计的内容；'
            '不要要求用户先指定速度环/位置环/电流环、pid/mit/smc、PWM 频率或具体控制结构。'
            '如果用户只给出应用场景或模糊目标，也要给出合理工程假设并继续整理需求。'
            '重点聚焦以下内容：'
            '1) 根据场景推断是否需要电流环（current_loop），并明确目标、约束、动态响应与可测量量；'
            '2) 根据场景推断机械环（mech_loop）的控制目标与结构层级（速度或位置）；'
            '3) 根据目标自行选择机械环控制方法（pid/mit/smc）并写出选择依据；'
            '4) 明确内外环关系、必要信号链路与关键性能指标。'
            '默认工程假设：吸尘器/风机/泵类驱动按高速 BLDC/PMSM 速度控制处理；'
            '伺服驱动按 PMSM 位置-速度-电流级联处理；电流环驱动按 PMSM FOC 电流环处理；'
            '一般“电机驱动器”默认按 PMSM/BLDC FOC 速度外环加电流内环处理。'
            '用户说“响应速度快”时，默认理解为速度外环响应快且电流内环带宽充足；'
            '用户说“低噪音/噪音低”时，默认转化为 SVPWM、较低电流纹波、平滑限幅和合理较高 PWM 频率约束；'
            '不要追问“响应速度快指哪个环”或“低噪音是否需要指定 PWM 频率”。'
            '如果使用了默认假设，请在完善后的需求文本中自然写出“默认假设：...”，然后继续给出可生成需求。'
            '如果用户提到 candidate_01/candidate_02/候选1/候选2 等候选方案设置，例如高生成温度、低生成温度、偏滑模、偏前馈、偏抗扰，请保留为“候选方案设置：...”文本；'
            '如果用户没有指定候选方案设置，则说明沿用默认四策略：稳健低超调、快速响应、抗扰恢复、平滑低纹波。'
            '只有当用户完全没有提供可识别的应用场景、控制对象或控制目标时，才输出一条以“NEED_MORE_INFO:”开头的追问。'
            '输出要求：信息充分时仅输出“完善后的需求文本”；信息不足时仅输出 NEED_MORE_INFO 追问；'
            '完善后的需求文本需要按语义分段输出，每段聚焦一个主题，例如控制对象、默认假设、控制目标、环路结构、控制方法、PWM策略、信号链路、性能指标、候选方案设置；'
            '不要输出代码块，不要输出额外解释。'
        )

    def _start_program_requirement_refinement(self, text: str, append_user: bool = True):
        self._pending_program_text = text
        self._program_requirement_before_refine = self.current_requirement
        if append_user:
            self._append_chat('user', text)
        self._apply_candidate_profile_overrides(text)

        if self._welcome_is_active():
            self.show_main_content()
        self._set_progress('正在整理控制程序需求...')
        self.chat_view.show_thinking()
        self._set_status_text('状态：对话处理中...')
        self.send_btn.setEnabled(False)
        self._chat_task = 'program_refine'

        self.chat_worker = ChatWorker(text, self._program_requirement_prompt(), self)
        self.chat_worker.success.connect(self.on_chat_success)
        self.chat_worker.failure.connect(self.on_chat_failure)
        self.chat_worker.finished.connect(self.on_chat_finished)
        self.chat_worker.start()

    def _on_welcome_input(self):
        text = self.welcome_input.text().strip()
        if not text:
            return
        self._start_program_requirement_refinement(text, append_user=True)
        self.welcome_input.clear()

    def _apply_quick_template(self, template_type):
        templates = {
            'PID转速控制': '请设计基于PID的电机转速控制程序。',
            'LADRC转速控制': '请设计基于LADRC的电机转速控制程序。',
            '位置伺服控制': '请设计基于位置环的伺服控制系统。'
        }
        
        template_text = templates.get(template_type, '')
        if template_text:
            self.welcome_input.setText(template_text)
            self._on_welcome_input()

    def _append_chat(self, role: str, text: str):
        role = self._normalize_chat_role(role)
        if role == 'assistant':
            self.chat_view.hide_thinking()
        self.chat_view.append_message(role, text)
        if role != 'debug':
            self.chat_history.append({
                'role': role,
                'text': text,
                'timestamp': QDateTime.currentDateTime().toString(Qt.ISODate)
            })
            self._save_chat_record()

    @staticmethod
    def _normalize_chat_role(role: str) -> str:
        role = (role or 'assistant').strip().lower()
        if role in {'model', 'system', 'notice', 'success', 'error'}:
            return 'assistant'
        if role in {'progress', 'debug'}:
            return 'debug'
        if role in {'user', 'assistant'}:
            return role
        return 'assistant'

    def _append_notice(self, text: str):
        self._append_chat('assistant', text)

    def _append_success(self, text: str):
        self._append_chat('assistant', text)

    def _append_error(self, text: str, detail: str = ''):
        self._append_chat('assistant', text)
        if detail:
            self._append_debug(detail)

    def _append_debug(self, text: str):
        self._append_chat('debug', text)

    def _set_progress(self, text: str):
        self._set_status_text(f'状态：{text}')

    def _flow_state(self):
        return {
            'program_requirement': self.current_requirement,
            'program_generated': self._has_generated_program(),
            'load_curve_saved': self._has_load_curve_saved(),
            'metrics_ready': self._has_metrics_ready(),
            'tuning_started': self._auto_tuning_started,
        }

    def _route_user_message_with_agent(self, text: str):
        if self.route_worker is not None and self.route_worker.isRunning():
            self._append_notice('正在理解上一条输入，请稍后。')
            return

        self._pending_route_text = text
        self._set_progress('正在判断对话意图...')
        self.send_btn.setEnabled(False)
        self.route_worker = FlowRouteWorker(text, self._flow_state(), list(self.chat_history), self)
        self.route_worker.routed.connect(self._on_route_success)
        self.route_worker.failure.connect(self._on_route_failure)
        self.route_worker.finished.connect(self._on_route_finished)
        self.route_worker.start()

    def _on_route_success(self, route: dict):
        text = self._pending_route_text
        self._pending_route_text = ''
        self._handle_user_route(text, route)

    def _on_route_failure(self, error_text: str):
        text = self._pending_route_text
        self._pending_route_text = ''
        fallback = self._fallback_route(text)
        self._append_notice('意图判断暂时不可用，已使用本地规则继续。')
        self._append_debug(f'意图判断失败：{error_text}')
        self._handle_user_route(text, fallback)

    def _on_route_finished(self):
        if not self._assistant_busy():
            self.send_btn.setEnabled(True)

    def _fallback_route(self, text: str) -> dict:
        state = self._flow_state()
        route = heuristic_route(text, state)
        if route:
            return route
        if not state.get('program_generated'):
            return {
                'action': ACTION_CLARIFY,
                'reply': '请描述原始应用场景或控制目标，例如PID转速控制、LADRC转速控制、位置伺服控制、电流环控制或调速驱动。',
                'reason': '缺少可整理的程序需求',
            }
        if state.get('load_curve_saved') and not state.get('metrics_ready'):
            return {'action': ACTION_SUBMIT_METRICS, 'reason': '默认作为指标需求处理'}
        return {'action': ACTION_ANSWER_QUESTION, 'reason': '默认作为普通问题回答'}

    def _handle_user_route(self, text: str, route: dict):
        action = (route or {}).get('action') or ACTION_CLARIFY
        reply = (route or {}).get('reply') or ''

        if self._needs_intent_confirmation(action):
            self._append_chat('user', text)
            self.input_edit.clear()
            self._append_intent_confirm_card(text, route)
            return

        if action == ACTION_CONFIRM_GENERATE:
            self._append_chat('user', text)
            self.input_edit.clear()
            self.generate_program()
            return

        if action == ACTION_REVISE_PROGRAM:
            self.input_edit.clear()
            self._start_program_requirement_refinement(text, append_user=True)
            return

        if action == ACTION_SHOW_LOAD_CURVE:
            self._append_chat('user', text)
            self.input_edit.clear()
            self.show_load_curve_card(announce=True, force=True)
            self._set_status_text('状态：等待负载曲线')
            return

        if action == ACTION_SUBMIT_METRICS:
            if not self._has_generated_program():
                self.input_edit.clear()
                self._start_program_requirement_refinement(text, append_user=True)
                return
            self.send_metric_requirement(text)
            return

        if action == ACTION_START_TUNING:
            self._append_chat('user', text)
            self.input_edit.clear()
            normalized = ''.join(text.strip().lower().split())
            explicit_restart = any(term in normalized for term in ('调优', '优化', '迭代参数', '重新', '再跑', '再运行'))
            if self._auto_tuning_started and not explicit_restart:
                self._append_chat('assistant', 'Optimize Agent 已经启动。你可以继续询问结果、修改负载曲线或补充指标；如果需要重新运行，请明确输入“重新调优”。')
                self._set_status_text('状态：调优已启动')
                return
            self._auto_start_tuning_if_ready(force=True, confirmed=True)
            return

        if action == ACTION_CONTINUE_NEXT_ROUND:
            self._append_chat('user', text)
            self.input_edit.clear()
            self._handle_continue_next_round()
            return

        if action == ACTION_ANSWER_QUESTION:
            self._append_chat('user', text)
            self.input_edit.clear()
            if reply:
                self._append_chat('assistant', reply)
                self._set_status_text('状态：已回答')
            else:
                self._start_answer_response(text)
            return

        self._append_chat('user', text)
        self.input_edit.clear()
        self._append_chat('assistant', reply or '我需要再确认一下你的意图。你是想修改程序需求、重画负载曲线，还是输入指标需求？')
        self._set_status_text('状态：等待澄清')

    def _needs_intent_confirmation(self, action: str) -> bool:
        if action in {ACTION_CONFIRM_GENERATE, ACTION_SUBMIT_METRICS, ACTION_START_TUNING}:
            return True
        return action == ACTION_REVISE_PROGRAM and self._has_generated_program()

    def _append_intent_confirm_card(self, text: str, route: dict):
        action = (route or {}).get('action') or ACTION_CLARIFY
        intent_title = self._intent_title(action)
        summary = self._intent_summary(action, text)
        confirm_label = self._intent_confirm_label(action)
        alternative_action = self._intent_alternative_action(action)
        alternative_label = self._intent_alternative_label(action)

        card = IntentConfirmCard(
            intent_title=intent_title,
            summary=summary,
            confirm_label=confirm_label,
            alternative_label=alternative_label,
            on_confirm=lambda: self._execute_confirmed_route(text, action),
            on_alternative=lambda: self._execute_confirmed_route(text, alternative_action),
            on_cancel=lambda: self._cancel_intent_confirmation(),
        )
        self.chat_view.append_widget(card, width_ratio=0.78)
        self._set_status_text('状态：等待确认意图')

    def _intent_title(self, action: str) -> str:
        titles = {
            ACTION_CONFIRM_GENERATE: '生成控制程序',
            ACTION_SUBMIT_METRICS: '补充性能指标',
            ACTION_START_TUNING: '启动调优任务',
            ACTION_REVISE_PROGRAM: '修改程序需求',
        }
        return titles.get(action, '继续当前操作')

    def _intent_confirm_label(self, action: str) -> str:
        labels = {
            ACTION_CONFIRM_GENERATE: '确认生成',
            ACTION_SUBMIT_METRICS: '确认写入',
            ACTION_START_TUNING: '确认启动',
            ACTION_REVISE_PROGRAM: '确认修改',
        }
        return labels.get(action, '确认')

    def _intent_alternative_action(self, action: str) -> str:
        if action == ACTION_REVISE_PROGRAM:
            return ACTION_SUBMIT_METRICS
        return ACTION_REVISE_PROGRAM

    def _intent_alternative_label(self, action: str) -> str:
        if action == ACTION_REVISE_PROGRAM:
            return '我要修改指标'
        return '我要修改程序'

    def _intent_summary(self, action: str, text: str) -> str:
        cleaned = ' '.join((text or '').split())
        if action == ACTION_CONFIRM_GENERATE:
            base = self.current_requirement or cleaned or '按当前已确认需求生成 candidate 控制器程序。'
        elif action == ACTION_START_TUNING:
            base = cleaned or '使用已收集的控制程序、负载曲线和需求指标启动 Optimize Agent。'
        else:
            base = cleaned or '继续处理当前输入。'
        if len(base) > 160:
            return base[:157] + '...'
        return base

    def _cancel_intent_confirmation(self):
        self._append_notice('已取消本次操作。你可以重新输入，或换一种说法继续。')
        self._set_status_text('状态：已取消')

    def _execute_confirmed_route(self, text: str, action: str):
        if action == ACTION_CONFIRM_GENERATE:
            self.generate_program()
            return

        if action == ACTION_REVISE_PROGRAM:
            self._start_program_requirement_refinement(text, append_user=False)
            return

        if action == ACTION_SUBMIT_METRICS:
            if not self._has_generated_program():
                self._append_notice('控制程序尚未生成，我会先把这条作为程序需求补充。')
                self._start_program_requirement_refinement(text, append_user=False)
                return
            self.send_metric_requirement(text, echo_user_external=False)
            return

        if action == ACTION_START_TUNING:
            self._start_tuning_from_text(text)
            return

        self._append_notice('已确认，但当前动作无法执行。请重新输入。')

    def _start_tuning_from_text(self, text: str):
        normalized = ''.join(text.strip().lower().split())
        explicit_restart = any(term in normalized for term in ('调优', '优化', '迭代参数', '重新', '再跑', '再运行'))
        if self._auto_tuning_started and not explicit_restart:
            self._append_chat('assistant', 'Optimize Agent 已经启动。你可以继续询问结果、修改负载曲线或补充指标；如果需要重新运行，请明确输入“重新调优”。')
            self._set_status_text('状态：调优已启动')
            return
        self._auto_start_tuning_if_ready(force=True, confirmed=True)

    def _answer_prompt(self):
        state = self._flow_state()
        state_text = json.dumps(state, ensure_ascii=False, indent=2)
        return (
            '你是 MotorAI 电机控制程序生成工作台中的对话助手。'
            '请回答用户关于当前项目、程序需求、负载曲线、指标或调优流程的问题。'
            '回答要简洁、具体，不要擅自推进生成程序、负载曲线、指标处理或调优。'
            '如果回答超过两句话，请按段落或短列表组织，避免输出一整段难以阅读的长文本。'
            f'当前工作流状态：\n{state_text}'
        )

    def _start_answer_response(self, text: str):
        self._set_progress('正在回答问题...')
        self.send_btn.setEnabled(False)
        self._chat_task = 'answer'
        self.chat_view.show_thinking()
        self.chat_worker = ChatWorker(text, self._answer_prompt(), self)
        self.chat_worker.success.connect(self.on_chat_success)
        self.chat_worker.failure.connect(self.on_chat_failure)
        self.chat_worker.finished.connect(self.on_chat_finished)
        self.chat_worker.start()

    def send_requirement(self):
        text = self.input_edit.toPlainText().strip()
        if not text:
            return
        if self.program_worker is not None and self.program_worker.isRunning():
            self._append_notice('正在生成控制程序，请稍后。')
            return
        if self.chat_worker is not None and self.chat_worker.isRunning():
            self._append_notice('正在等待上一条对话返回，请稍后。')
            return
        if self.route_worker is not None and self.route_worker.isRunning():
            self._append_notice('正在理解上一条输入，请稍后。')
            return

        route = heuristic_route(text, self._flow_state())
        if route is not None:
            self._handle_user_route(text, route)
            return

        self._route_user_message_with_agent(text)

    def send_metric_requirement(self, text: str, echo_user_external: bool = True):
        if self.requirement_panel is None:
            self._append_error('需求指标处理器尚未初始化。')
            return
        if getattr(self.requirement_panel, 'chat_worker', None) is not None and self.requirement_panel.chat_worker.isRunning():
            self._append_notice('正在等待上一条指标需求返回，请稍后。')
            return

        submitted = self.requirement_panel.submit_requirement_text(
            text,
            append_user=True,
            echo_user_external=echo_user_external,
        )
        if submitted:
            self.chat_view.show_thinking()
            self.send_btn.setEnabled(False)
            self.input_edit.clear()

    def _project_json_path(self):
        if callable(self.project_json_getter):
            return self.project_json_getter()
        return None

    def _project_data(self):
        project_json = self._project_json_path()
        if not project_json:
            return {}
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _has_generated_program(self):
        data = self._project_data()
        candidate_dirs = self._candidate_dirs()
        if candidate_dirs:
            required_names = ('ctl_main.c', 'ctl_main.h', 'paras.generated.h')
            for candidate_dir in candidate_dirs:
                src_dir = candidate_dir / 'src'
                if not all((src_dir / name).exists() for name in required_names):
                    return False
            return True

        candidate_generation = data.get('candidate_generation')
        if isinstance(candidate_generation, list) and candidate_generation:
            for item in candidate_generation:
                if not isinstance(item, dict):
                    return False
                paths = [item.get('ctl_main_c'), item.get('ctl_main_h'), item.get('paras_header')]
                if not all(path and Path(str(path)).exists() for path in paths):
                    return False
            return True

        return False

    def _has_load_curve_saved(self):
        if self.load_curve_panel is not None and hasattr(self.load_curve_panel, '_simulate_folder'):
            try:
                return (self.load_curve_panel._simulate_folder() / 'load.csv').exists()
            except Exception:
                return False
        return False

    def _has_metrics_ready(self):
        data = self._project_data()
        return bool(data.get('objective') or data.get('metrics') or data.get('targets'))

    def _assistant_busy(self):
        if self.chat_worker is not None and self.chat_worker.isRunning():
            return True
        if self.route_worker is not None and self.route_worker.isRunning():
            return True
        if self.program_worker is not None and self.program_worker.isRunning():
            return True
        if self.requirement_panel is not None:
            worker = getattr(self.requirement_panel, 'chat_worker', None)
            if worker is not None and worker.isRunning():
                return True
        return False

    def _auto_start_tuning_if_ready(self, force: bool = False, announce: bool = True, confirmed: bool = False):
        missing = []
        if not self._has_generated_program():
            missing.append('控制程序')
        if not self._has_load_curve_saved():
            missing.append('负载曲线')
        if not self._has_metrics_ready():
            missing.append('需求指标')

        if missing:
            if announce:
                self._append_notice(f'还缺少{"、".join(missing)}，暂不启动调优。')
            return False

        if self._auto_tuning_started and not force:
            return True

        if not confirmed:
            if announce:
                self._append_auto_tuning_confirm_card()
            return False

        self._auto_tuning_confirm_pending = False
        self._auto_tuning_started = True
        self._workflow_steps.add('tuning_started')
        self._append_success('控制程序、负载曲线和需求指标已收集完成，开始启动 Optimize Agent。')
        self._set_progress('正在启动调优...')
        if callable(self.run_tuning_callback):
            self.run_tuning_callback()
        else:
            self._append_error('调优入口尚未初始化，无法启动 Optimize Agent。')
        return True

    def _append_auto_tuning_confirm_card(self):
        if self._auto_tuning_confirm_pending or self._auto_tuning_started:
            return
        self._auto_tuning_confirm_pending = True
        card = IntentConfirmCard(
            intent_title='启动自动调优',
            summary='控制程序、负载曲线和需求指标已准备好。是否现在启动 Optimize Agent？',
            confirm_label='启动调优',
            alternative_label='',
            on_confirm=self._confirm_auto_tuning_start,
            on_alternative=None,
            on_cancel=self._cancel_auto_tuning_start,
        )
        self.chat_view.append_widget(card, width_ratio=0.78)
        self._set_status_text('状态：等待确认是否启动调优')

    def _confirm_auto_tuning_start(self):
        self._auto_tuning_confirm_pending = False
        self._auto_start_tuning_if_ready(force=True, announce=True, confirmed=True)

    def _cancel_auto_tuning_start(self):
        self._auto_tuning_confirm_pending = False
        self._append_notice('已暂缓启动调优。准备好后可以输入“启动调优”。')
        self._set_status_text('状态：调优已暂缓')

    def _update_project_json_requirement(self, requirement_text: str):
        project_json = self._project_json_path()
        if not project_json:
            return
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
            data['objective_text'] = requirement_text
            with open(project_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            write_common_requirement_snapshot(Path(project_json), data)
            for candidate_dir in self._candidate_dirs():
                candidate_json = candidate_dir / 'candidate.json'
                if not candidate_json.exists():
                    continue
                with open(candidate_json, 'r', encoding='utf-8') as f:
                    candidate_data = json.load(f)
                if isinstance(candidate_data, dict):
                    candidate_data['objective_text'] = requirement_text
                    with open(candidate_json, 'w', encoding='utf-8') as f:
                        json.dump(candidate_data, f, ensure_ascii=False, indent=2)
            self._append_debug('需求已保存到当前项目。')
        except Exception as exc:
            self._append_error('需求保存失败。', str(exc))

    def _apply_candidate_profile_overrides(self, text: str):
        project_json = self._project_json_path()
        if not project_json:
            return
        try:
            result = apply_candidate_profile_overrides(Path(project_json), text)
            updated = result.get('updated') if isinstance(result, dict) else None
            if updated:
                profiles_path = result.get('profiles_path', '')
                self._append_debug(f'已更新候选生成策略：{", ".join(updated)}。策略文件：{profiles_path}')
        except Exception as exc:
            self._append_error('更新 candidate 策略失败。', str(exc))

    def _candidate_dirs(self):
        project_json = self._project_json_path()
        if not project_json:
            return []
        try:
            return discover_candidate_dirs(Path(project_json), ['all'])
        except Exception:
            return []

    @staticmethod
    def _candidate_profile(index: int) -> dict:
        return candidate_design_profile(index)

    def _load_candidate_profile(self, candidate_dir: Path, index: int) -> dict:
        profile = self._candidate_profile(index)
        candidate_json = candidate_dir / 'candidate.json'
        if not candidate_json.exists():
            return profile
        try:
            with open(candidate_json, 'r', encoding='utf-8') as f:
                candidate_data = json.load(f)
            candidate_profile = candidate_data.get('design_profile') if isinstance(candidate_data, dict) else None
            if isinstance(candidate_profile, dict):
                merged = dict(profile)
                merged.update(candidate_profile)
                return merged
        except Exception:
            pass
        return profile

    @staticmethod
    def _build_tuning_policy_from_loops(selected_loops):
        return _build_tuning_policy_from_loops(selected_loops)

    def _write_candidate_generated_result(self, candidate_dir: Path, loop_ids_path: Path, profile: dict):
        with open(loop_ids_path, 'r', encoding='utf-8') as f:
            loops_payload = json.load(f)
        if not isinstance(loops_payload, dict):
            return {}

        candidate_json = candidate_dir / 'candidate.json'
        with open(candidate_json, 'r', encoding='utf-8') as f:
            candidate_data = json.load(f)
        if not isinstance(candidate_data, dict):
            candidate_data = {}

        selected_loops = loops_payload.get('selected_loops') or []
        candidate_data['selected_loops'] = selected_loops
        candidate_data['generated_loop_ids_path'] = str(loop_ids_path)
        candidate_data['design_profile'] = profile
        candidate_data['tuning_policy'] = self._build_tuning_policy_from_loops(selected_loops)
        candidate_data.setdefault('paths', {})
        candidate_data['paths']['header_path'] = 'src/paras.generated.h'
        candidate_data['paths']['result_file'] = 'log/optimize/tuning_result.json'
        with open(candidate_json, 'w', encoding='utf-8') as f:
            json.dump(candidate_data, f, ensure_ascii=False, indent=2)

        configure_candidate_optimize(candidate_json)
        return candidate_data

    def _update_project_json_selected_loops(self, loop_ids_path: Path):
        project_json = self._project_json_path()
        if not project_json:
            return
        try:
            with open(loop_ids_path, 'r', encoding='utf-8') as f:
                loops_payload = json.load(f)
            if not isinstance(loops_payload, dict):
                return

            with open(project_json, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
            if not isinstance(project_data, dict):
                project_data = {}

            project_data['selected_loops'] = loops_payload.get('selected_loops') or []
            project_data['generated_loop_ids_path'] = str(loop_ids_path)
            paths = project_data.get('paths')
            if not isinstance(paths, dict):
                paths = {}
                project_data['paths'] = paths
            paths['generated_loop_ids_path'] = str(loop_ids_path)

            with open(project_json, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, ensure_ascii=False, indent=2)
            self._append_debug('主程序结构已保存到当前项目。')
            self._generate_tuning_policy()
        except Exception as exc:
            self._append_error('主程序结构保存失败。', str(exc))

    def _generate_tuning_policy(self):
        project_json = self._project_json_path()
        if not project_json:
            return
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            selected_loops = data.get('selected_loops', [])
            data['tuning_policy'] = self._build_tuning_policy_from_loops(selected_loops)
            with open(project_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._append_debug('调参策略已准备好。')
        except Exception as exc:
            self._append_error('调参策略生成失败。', str(exc))

    def _candidate_plan_text(self):
        candidate_dirs = self._candidate_dirs()
        if candidate_dirs:
            plan_lines = ['需求已整理。各 candidate 的生成侧重如下；确认无误后回复“生成程序”：']
            for index, candidate_dir in enumerate(candidate_dirs, start=1):
                profile = self._load_candidate_profile(candidate_dir, index)
                name = profile.get('name') or candidate_dir.name
                structure_bias = profile.get('structure_bias') or '沿用默认结构生成策略。'
                implementation_bias = profile.get('implementation_bias') or '按当前模板生成 ctl_main.c、ctl_main.h 和 paras.generated.h。'
                methods = profile.get('preferred_control_methods') or []
                method_text = '、'.join(str(item) for item in methods) if methods else '默认方法'
                plan_lines.append(f'{candidate_dir.name}：{name}；结构侧重：{structure_bias}；候选方法：{method_text}；代码侧重：{implementation_bias}')
        else:
            plan_lines = ['需求已整理，当前可以生成控制程序。确认无误后回复“生成程序”；如果还要补充，请直接继续输入。']
        return '\n'.join(plan_lines)

    def on_chat_success(self, reply: str):
        self.chat_view.hide_thinking()
        if self._chat_task == 'answer':
            self._append_chat('assistant', reply)
            self._set_status_text('状态：已回答')
            return

        if self._chat_task == 'program_refine' and self._is_requirement_clarification(reply):
            self.current_requirement = self._program_requirement_before_refine
            self._append_chat('assistant', self._clean_requirement_clarification(reply))
            self._set_status_text('状态：等待补充原始需求')
            return

        self._append_chat('assistant', reply)
        self._apply_candidate_profile_overrides(reply)
        self.current_requirement = reply
        self._update_project_json_requirement(reply)
        self._append_chat('assistant', self._candidate_plan_text())
        self._set_program_input_mode()
        self._set_status_text('状态：等待确认生成程序')

    @staticmethod
    def _is_requirement_clarification(reply: str) -> bool:
        text = (reply or '').strip()
        if text.upper().startswith('NEED_MORE_INFO'):
            return True
        clarification_terms = (
            '请提供原始需求',
            '请补充原始需求',
            '请补充需求',
            '需要更多信息',
            '无法生成',
            '无法完善',
        )
        return len(text) <= 120 and any(term in text for term in clarification_terms)

    @staticmethod
    def _clean_requirement_clarification(reply: str) -> str:
        text = (reply or '').strip()
        for marker in ('NEED_MORE_INFO:', 'NEED_MORE_INFO：'):
            if text.upper().startswith(marker):
                return text[len(marker):].strip() or '请描述原始应用场景或控制目标，例如吸尘器驱动、伺服位置控制、电流环控制或调速驱动。'
        return text or '请描述原始应用场景或控制目标，例如吸尘器驱动、伺服位置控制、电流环控制或调速驱动。'

    def on_chat_failure(self, error_text: str):
        self.chat_view.hide_thinking()
        self._append_error('对话失败，请检查设置与网络。', error_text)
        self._set_status_text('状态：对话失败，请检查设置与网络')

    def on_chat_finished(self):
        self.chat_view.hide_thinking()
        self._chat_task = None
        if not self._assistant_busy():
            self.send_btn.setEnabled(True)

    def generate_program(self):
        if self.program_worker is not None and self.program_worker.isRunning():
            self._append_notice('正在生成控制程序，请稍后。')
            return

        if not self.current_requirement:
            self._append_notice('请先输入并发送需求，再执行生成。')
            self._set_status_text('状态：缺少需求')
            return

        template_dir = GENERATE_ROOT / 'Example'
        project_json = self._project_json_path()
        llm_config = MOTORAI_ROOT / 'motorai_settings.json'
        candidate_dirs = self._candidate_dirs()

        if not project_json or not candidate_dirs:
            self._append_error('未找到 candidate 工作区。请重新新建竞争模式工程。')
            self._set_status_text('状态：缺少 candidate')
            return
        for template_name in ('ctl_main.c', 'ctl_main.h', 'paras.h'):
            template_path = template_dir / template_name
            if not template_path.exists():
                self._append_error('生成模板不存在。', str(template_path))
                self._set_status_text('状态：生成模板缺失')
                return

        self._set_progress(f'正在为 {len(candidate_dirs)} 个 candidate 生成控制器程序...')
        self.chat_view.show_thinking('正在思考中，正在生成控制程序...')
        self.send_btn.setEnabled(False)
        self.run_btn.setEnabled(False)

        self.program_worker = GenerateProgramWorker(
            requirement=self.current_requirement,
            project_json=Path(project_json),
            candidate_dirs=candidate_dirs,
            template_dir=template_dir,
            llm_config=llm_config,
            parent=self,
        )
        self.program_worker.progress.connect(self._set_progress)
        self.program_worker.debug.connect(self._append_debug)
        self.program_worker.success.connect(self._on_program_generation_success)
        self.program_worker.failure.connect(self._on_program_generation_failure)
        self.program_worker.finished.connect(self._on_program_generation_finished)
        self.program_worker.start()

    def _on_program_generation_success(self, result: dict):
        self._set_status_text('状态：生成完成')
        self._append_debug('所有 candidate 控制器程序已生成。根目录 src 未被修改。')
        if callable(self.structure_refresh_callback):
            self.structure_refresh_callback()
        self.show_load_curve_card()

    def _on_program_generation_failure(self, error_text: str):
        self._set_status_text('状态：调用失败')
        self._append_error('生成过程中发生异常。', error_text)

    def _on_program_generation_finished(self):
        self.chat_view.hide_thinking()
        self.send_btn.setEnabled(True)
        self.run_btn.setEnabled(True)
        worker = self.program_worker
        self.program_worker = None
        if worker is not None:
            worker.deleteLater()

    def _handle_continue_next_round(self):
        """处理继续下一轮的请求：发现最新完成的轮次，生成下一轮策略并启动调优。"""
        import inspect
        project_json_path = self._project_json_path()
        if not project_json_path:
            self._append_error('未找到项目 JSON，无法继续下一轮。')
            return
        project_dir = Path(project_json_path).parent
        rounds_root = project_dir / 'rounds'
        current_round = 0
        if rounds_root.exists():
            import re
            for d in sorted(rounds_root.glob('round_*'), reverse=True):
                if (d / 'round_feedback.json').exists():
                    m = re.search(r'round_(\d+)', d.name)
                    if m:
                        current_round = int(m.group(1))
                    break
        if current_round <= 0:
            self._append_error('未找到已完成轮次的 round_feedback.json，请先完整运行一轮调优。')
            return
        next_round = current_round + 1
        next_profiles = rounds_root / f'round_{next_round:02d}' / 'candidate_profiles.json'
        if not next_profiles.exists():
            self._append_debug(f'正在生成第 {next_round} 轮方案策略（需要调用 LLM）...')
            try:
                from Competition.next_round_strategy import generate_next_round_strategy
                generate_next_round_strategy(project_json_path,
                                             from_round=current_round,
                                             to_round=next_round)
            except Exception as exc:
                self._append_error(f'无法生成第 {next_round} 轮策略：{exc}')
                return
        self._append_notice(f'正在启动第 {next_round} 轮调优（将自动 generate + optimize）...')
        if callable(self.run_tuning_callback):
            try:
                sig = inspect.signature(self.run_tuning_callback)
                if 'round_number' in sig.parameters:
                    self.run_tuning_callback(round_number=next_round)
                else:
                    self.run_tuning_callback()
            except Exception as exc:
                self._append_error(f'启动第 {next_round} 轮调优失败：{exc}')

    def _project_folder(self):
        if callable(self.project_json_getter):
            pj = self.project_json_getter()
            if pj:
                try:
                    return Path(pj).parent
                except Exception:
                    pass
        return None

    def _save_chat_record(self):
        project_folder = self._project_folder()
        if project_folder is None:
            return
        record_path = project_folder / 'record.json'
        try:
            data = {}
            if record_path.exists():
                with open(record_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            data['main_program'] = self.chat_history
            with open(record_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_chat_record(self):
        self._detach_workflow_panels()
        self.chat_view.clear_messages()
        self.chat_history = []
        self._workflow_steps.clear()
        self._load_curve_card_count = 0
        self._auto_tuning_confirm_pending = False

        project_folder = self._project_folder()
        if project_folder is None:
            return
        record_path = project_folder / 'record.json'
        if not record_path.exists():
            return
        try:
            with open(record_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.chat_history = data.get('main_program', [])
            for msg in self.chat_history:
                self.chat_view.append_message(msg.get('role', 'system'), msg.get('text', ''))
        except Exception:
            pass

    def reload_for_project(self):
        self.current_requirement = ''
        self._auto_tuning_started = False
        self._auto_tuning_confirm_pending = False
        self._load_chat_record()
        self._set_program_input_mode()
        if not self.chat_history and not self._project_has_workflow_state():
            self.show_welcome_overlay()
            return
        self.show_main_content()
        self._restore_workflow_from_project()

    def _project_has_workflow_state(self):
        project_json = self._project_json_path()
        if not project_json:
            return False

        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}

        if isinstance(data, dict):
            for key in ('objective_text', 'objective', 'selected_loops', 'metrics', 'targets'):
                value = data.get(key)
                if value:
                    return True

        if self.load_curve_panel is not None and hasattr(self.load_curve_panel, '_simulate_folder'):
            try:
                return (self.load_curve_panel._simulate_folder() / 'load.csv').exists()
            except Exception:
                return False

        return False

    def _restore_workflow_from_project(self):
        project_json = self._project_json_path()
        if not project_json:
            return
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}

        if isinstance(data, dict):
            self.current_requirement = str(data.get('objective_text') or self.current_requirement or '').strip()

        selected_loops = data.get('selected_loops') if isinstance(data, dict) else None
        if isinstance(selected_loops, list) and selected_loops:
            self.show_load_curve_card(announce=False)

        has_load_curve = self._has_load_curve_saved()
        if has_load_curve:
            self._set_metric_input_mode()

        if isinstance(data, dict) and (data.get('objective') or data.get('metrics') or data.get('targets')):
            self._set_status_text('状态：信息已准备，可继续提问或输入“重新调优”启动优化')

