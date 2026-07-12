from PyQt5.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
    QVBoxLayout,
)
from PyQt5.QtCore import Qt, QDateTime
import json
import math
from pathlib import Path

import core.paths  # ensures repository roots are on sys.path
from styles.theme import (
    RADIUS_CARD,
    current_theme,
    primary_button_qss,
    status_label_qss,
)
from widgets.chat import ChatInputEdit, ChatStreamWidget, ChatWorker, call_ui_chat_model
from Competition.competition_workspace import write_common_requirement_snapshot


class RequirementPanel(QWidget):
    def __init__(self, project_json_getter=None, parent=None):
        super().__init__(parent)
        self.chat_worker = None
        self.project_json_getter = project_json_getter
        self.chat_history = []
        self.completion_callback = None
        self.external_chat_callback = None
        self.external_status_callback = None
        self._last_user_input = None
        self.external_finished_callback = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.chat_view = ChatStreamWidget()
        self._append_notice('请输入需求指标。')

        self.input_edit = ChatInputEdit()
        self.input_edit.setPlaceholderText('请输入需求指标描述...')
        self.input_edit.setFixedHeight(72)
        self.input_edit.enterPressed.connect(self.send_requirement)

        self.send_btn = QPushButton('发送需求')
        self.send_btn.setObjectName('primaryButton')
        self.send_btn.setStyleSheet(primary_button_qss(padding='7px 14px'))
        self.send_btn.clicked.connect(self.send_requirement)

        self.clear_btn = QPushButton('清空')
        self.clear_btn.setObjectName('ghostButton')
        self.clear_btn.clicked.connect(self.input_edit.clear)

        self.status_label = QLabel('状态：等待输入需求指标')
        self.status_label.setObjectName('taskStatusLabel')
        self.status_label.setStyleSheet(status_label_qss())

        self.param_form = QWidget()
        self.param_form.setStyleSheet(f'background:{current_theme().panel};border-radius:{RADIUS_CARD}px;')
        param_layout = QVBoxLayout(self.param_form)
        param_layout.setContentsMargins(10, 10, 10, 10)
        param_layout.setSpacing(8)
        param_layout.addWidget(QLabel('目标参数设置'))
        
        self.param_table = QTableWidget()
        self.param_table.setColumnCount(3)
        self.param_table.setHorizontalHeaderLabels(['信号名称', '目标值', '单位'])
        self.param_table.horizontalHeader().setStretchLastSection(True)
        self.param_table.verticalHeader().setVisible(False)
        t = current_theme()
        self.param_table.setStyleSheet(
            f'QTableWidget{{background:{t.surface};border:1px solid {t.border};'
            f'border-radius:{RADIUS_CARD}px;}}'
            f'QHeaderView::section{{background:{t.header_bg};padding:4px;}}'
        )
        param_layout.addWidget(self.param_table)

        input_bar = QWidget()
        input_bar_layout = QHBoxLayout(input_bar)
        input_bar_layout.setContentsMargins(0, 0, 0, 0)
        input_bar_layout.setSpacing(10)
        input_bar_layout.addWidget(self.input_edit, 1)

        side_actions = QWidget()
        side_actions_layout = QVBoxLayout(side_actions)
        side_actions_layout.setContentsMargins(0, 0, 0, 0)
        side_actions_layout.setSpacing(8)
        side_actions_layout.addWidget(self.send_btn)
        side_actions_layout.addWidget(self.clear_btn)
        side_actions_layout.addStretch()
        input_bar_layout.addWidget(side_actions)

        layout.addWidget(QLabel('需求指标设置'))
        layout.addWidget(self.chat_view, 1)
        layout.addWidget(self.param_form, 1)
        layout.addWidget(input_bar)
        layout.addWidget(self.status_label)

    def set_completion_callback(self, callback):
        self.completion_callback = callback

    def set_external_callbacks(self, chat_callback=None, status_callback=None, finished_callback=None):
        self.external_chat_callback = chat_callback
        self.external_status_callback = status_callback
        self.external_finished_callback = finished_callback

    def _append_chat(self, role: str, text: str, echo_external: bool = True):
        role = self._normalize_chat_role(role)
        self.chat_view.append_message(role, text)
        if role != 'debug':
            self.chat_history.append({
                'role': role,
                'text': text,
                'timestamp': QDateTime.currentDateTime().toString(Qt.ISODate)
            })
            self._save_chat_record()
        if echo_external and callable(self.external_chat_callback):
            self.external_chat_callback(role, text)

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

    def _set_status_text(self, text: str):
        self.status_label.setText(text)
        if callable(self.external_status_callback):
            self.external_status_callback(text)

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
            data['requirement'] = self.chat_history
            with open(record_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_chat_record(self):
        self.chat_view.clear_messages()
        self.chat_history = []

        project_folder = self._project_folder()
        if project_folder is None:
            self.chat_view.append_message('assistant', '请输入需求指标。')
            return
        record_path = project_folder / 'record.json'
        if not record_path.exists():
            self.chat_view.append_message('assistant', '请输入需求指标。')
            return
        try:
            with open(record_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.chat_history = data.get('requirement', [])
            for msg in self.chat_history:
                self.chat_view.append_message(msg.get('role', 'system'), msg.get('text', ''))
        except Exception:
            pass
        if not self.chat_history:
            self.chat_view.append_message('assistant', '请输入需求指标。')

    def load_from_project_json(self):
        """Load targets and other UI state from the current project JSON.
        Called by the main window when a project is opened.
        """
        project_json = self._project_json_path()
        if not project_json:
            return
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            targets = data.get('targets', {})
            # ensure format: mapping signal -> {target_value, unit, description}
            if isinstance(targets, dict):
                self._update_param_table(targets)
        except Exception:
            pass

    def send_requirement(self):
        text = self.input_edit.toPlainText().strip()
        if self.submit_requirement_text(text):
            self.input_edit.clear()

    def submit_requirement_text(self, text: str, append_user: bool = True, echo_user_external: bool = True):
        if not text:
            return False
        if self.chat_worker is not None and self.chat_worker.isRunning():
            self._append_notice('正在等待上一条对话返回，请稍后。')
            return False

        project_json = self._project_json_path()
        if not project_json:
            QMessageBox.warning(self, '提示', '请先打开项目文件。')
            return False

        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
            selected_loops = project_data.get('selected_loops', [])
            if not selected_loops:
                QMessageBox.warning(self, '提示', '请先在“主程序生成”中生成并保存 loop-ids 结果。')
                return False
        except Exception as exc:
            QMessageBox.warning(self, '提示', f'读取项目文件失败：{exc}')
            return False

        if append_user:
            self._append_chat('user', text, echo_external=echo_user_external)
        self._last_user_input = text
        self._set_progress('正在整理需求指标...')
        self.chat_view.show_thinking()
        self.send_btn.setEnabled(False)

        loop_info = '\n'.join([f"- {loop.get('name', '')}: {loop.get('description', '')}" for loop in selected_loops])
        existing_objective = project_data.get('objective', '')

        user_input = f"控制器结构：\n{loop_info}\n\n"
        if existing_objective:
            user_input += f"当前已有的需求指标：\n{existing_objective}\n\n"
        user_input += f"用户新增需求：\n{text}\n\n请对已有需求指标和新增需求进行整合，输出一句完整的需求指标描述。"

        self.chat_worker = ChatWorker(
            user_input,
            (
                '你是面向 loop-ids 生成系统的需求指标完善助手。'
                '你的任务是根据给定的控制器结构，把用户输入改写为可执行、可测量、适合控制器设计验证的中文需求指标。'
                '性能指标包括：超调量、调整时间、上升时间、稳态误差。'
                '同时必须保留用户明确给出的工况参数，包括但不限于：目标转速（含 rpm 或 rad/s 数值）、'
                '目标转矩（含 N*m 数值）、目标电流 iq/id（含 A 数值）。\n\n'
                '整合规则（严格遵守）：\n'
                '1. 用户新增需求中的任何数值或描述，无条件覆盖已有需求指标中的同名参数。'
                '   例如已有"超调<10%"，用户新增"超调改成5%"→输出"超调<5%"，绝不输出10%。\n'
                '2. 用户新增需求中没提到的已有参数，保留原有值不变。\n'
                '3. 用户明确说"删除""去掉""不要"某个指标时，从整合结果中移除该指标。\n'
                '4. 冲突判定以用户意图为准，不要自行判断哪个值"更合理"。\n\n'
                '请在现有控制器结构的基础上设计指标，不要改变控制器结构。'
                '输出要求：用一句话简洁描述整合后的需求指标（含工况参数），不输出其他内容。'
            ),
            self,
        )
        self.chat_worker.success.connect(self.on_chat_success)
        self.chat_worker.failure.connect(self.on_chat_failure)
        self.chat_worker.finished.connect(self.on_chat_finished)
        self.chat_worker.start()
        return True

    def _project_json_path(self):
        if callable(self.project_json_getter):
            return self.project_json_getter()
        return None

    def _ctl_main_paths(self):
        project_json = self._project_json_path()
        if not project_json:
            self._append_debug('_ctl_main_paths: project_json 为 None，跳过。')
            return []

        paths = []
        seen = set()

        # 优先从 project JSON 的 candidate_generation 中读取路径
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            candidate_gen = data.get('candidate_generation')
            if isinstance(candidate_gen, list):
                for entry in candidate_gen:
                    if isinstance(entry, dict):
                        ctl_main = entry.get('ctl_main_c', '')
                        if ctl_main:
                            p = Path(ctl_main)
                            if p not in seen and p.exists():
                                seen.add(p)
                                paths.append(p)
        except Exception:
            pass

        if paths:
            self._append_debug(
                f'_ctl_main_paths: 从 candidate_generation 找到 {len(paths)} 个: '
                f'{[str(p) for p in paths]}'
            )
            return paths

        # 回退：文件系统搜索
        base_dir = project_json.parent
        candidates = [
            base_dir / 'ctl_main.c',
            base_dir / 'src' / 'ctl_main.c',
        ]
        try:
            for candidate_dir in sorted(base_dir.glob('candidate_*')):
                if candidate_dir.is_dir():
                    candidates.append(candidate_dir / 'src' / 'ctl_main.c')
        except OSError:
            pass

        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            if candidate.exists():
                paths.append(candidate)

        self._append_debug(
            f'_ctl_main_paths: base_dir={base_dir}, 候选路径数={len(candidates)}, '
            f'找到={len(paths)}: {[str(p) for p in paths]}'
        )
        return paths

    def _format_float_literal(self, value):
        literal = f'{value:.6f}'.rstrip('0').rstrip('.')
        if not literal:
            literal = '0'
        if '.' not in literal and 'e' not in literal.lower():
            literal = f'{literal}.0'
        return f'{literal}f'

    def _rewrite_target_velocity_literal(self, content, target_speed):
        import re

        velocity_value = target_speed / 3000.0 * 9.55
        velocity_literal = self._format_float_literal(velocity_value)

        pattern = r'(ctl_set_mech_target_velocity\(&mech_ctrl,\s*)([^)]*?)(\)\s*;)'

        def repl(match):
            return f'{match.group(1)}{velocity_literal}{match.group(3)}'

        updated_content, count = re.subn(pattern, repl, content, count=1)
        return updated_content, bool(count)

    def _write_requirement_to_project_json(self, requirement_text: str):
        project_json = self._project_json_path()
        if not project_json:
            return
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
            data['objective'] = requirement_text
            with open(project_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            write_common_requirement_snapshot(Path(project_json), data)
            self._append_debug('需求指标已保存到当前项目。')
        except Exception as exc:
            self._append_error('需求指标保存失败。', str(exc))

    METRICS_PARAM_TEMPLATES = {
        "overshoot": {
            "metric_name": "overshoot",
            "optimization_direction": "minimize",
            "normalize": True,
            "good_threshold": 0.10,
            "bad_threshold": 0.30,
            "description": "超调量，归一化后 0.10 表示 10%"
        },
        "settling_time": {
            "metric_name": "settling_time",
            "optimization_direction": "minimize",
            "tolerance_ratio": 0.05,
            "good_threshold": 0.20,
            "bad_threshold": 1.00,
            "description": "调节时间，进入并保持在目标值 ±5% 范围内所需时间"
        },
        "steady_state_error": {
            "metric_name": "steady_state_error",
            "optimization_direction": "minimize",
            "window": 0.10,
            "good_threshold": 15.708,
            "bad_threshold": 62.832,
            "description": "稳态误差，末尾 10% 数据窗口内的平均绝对误差"
        },
        "ripple": {
            "metric_name": "ripple",
            "optimization_direction": "minimize",
            "window": 0.10,
            "good_threshold": 0.02,
            "bad_threshold": 0.20,
            "description": "稳态纹波，末尾 10% 数据窗口内的峰峰值"
        },
        "rise_time": {
            "metric_name": "rise_time",
            "optimization_direction": "minimize",
            "lower_ratio": 0.10,
            "upper_ratio": 0.90,
            "good_threshold": 0.10,
            "bad_threshold": 1.00,
            "description": "上升时间，信号从目标值 10% 上升到 90% 所需时间"
        }
    }

    PHYSICAL_QUANTITIES = {
        "speed": {"signal": "rotor_speed_rad_s", "target_value": 314.16, "weight": 0.25},
        "torque": {"signal": "electromagnetic_torque_nm", "target_value": 0.2, "weight": 0.15},
        "iq": {"signal": "stator_iq_a", "target_value": 3.0, "weight": 0.15},
        "id": {"signal": "stator_id_a", "target_value": 0.0, "weight": 0.15}
    }

    def on_chat_success(self, reply: str):
        self.chat_view.hide_thinking()
        self._append_chat('assistant', reply)
        self._write_requirement_to_project_json(reply)
        self._set_progress('正在生成任务类型...')
        self._generate_task_type()
        self._set_progress('正在生成信号、目标和事件...')
        self._generate_signals_targets_events()
        self._set_progress('正在生成评价指标...')
        self._generate_metrics()
        self._set_progress('正在生成目标参数...')
        self._generate_targets_from_metrics()
        self._set_progress('正在生成停止条件...')
        self._generate_stop_conditions()
        self._set_status_text('状态：需求指标已完善')
        if callable(self.completion_callback):
            self.completion_callback()

    def _generate_task_type(self):
        project_json = self._project_json_path()
        if not project_json:
            return
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            objective_text = data.get('objective_text', '')
            system_prompt = (
                '你是需求分析助手。请根据用户需求文本，总结出一句话描述用户设计的是什么控制系统。'
                '输出要求：仅输出任务类型，例如："PMSM速度控制系统"、"PMSM位置控制系统"、"永磁同步电机转矩控制系统"等。'
                '不要输出其他内容。'
            )
            result = call_ui_chat_model(objective_text, system_prompt, temperature=0.2)
            data['task_type'] = result.strip()
            with open(project_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            self._append_error('任务类型生成失败。', str(exc))

    def _generate_signals_targets_events(self):
        project_json = self._project_json_path()
        if not project_json:
            return
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            objective_text = data.get('objective_text', '')
            objective = data.get('objective', '')
            
            system_prompt = (
                '你是控制器分析助手。请分析用户需求中是否涉及以下控制环路类型：\n\n'
                '1. 机械环/速度环/位置环：涉及速度、位置、转速等控制要求\n'
                '2. 电流环：涉及电流、iq、id等控制要求\n\n'
                '输出格式要求（严格遵守）：\n'
                '1. 只输出JSON数组格式，不输出任何其他文字、解释或说明\n'
                '2. JSON必须是有效的，可以被标准JSON解析器解析\n'
                '3. 数组元素只能是 "mechanical"（机械环）和/或 "current"（电流环）\n'
                '4. 如果两种环都涉及，输出 ["mechanical", "current"]\n'
                '5. 如果都不涉及，输出空数组 []\n\n'
                '用户需求：' + objective + '\n\n'
                '请输出JSON数组：'
            )
            
            parsed = None
            max_retries = 2
            for attempt in range(max_retries + 1):
                result = call_ui_chat_model(objective, system_prompt, temperature=0.2)
                
                self._append_debug(f'大模型返回（环路分析）：{result.strip()}')
                
                if not result or not result.strip():
                    if attempt < max_retries:
                        self._append_debug(f'第{attempt+1}次环路分析返回为空，重新调用。')
                        system_prompt = f'你上次返回了空内容。请重新输出正确的JSON数组格式。\n\n只输出JSON数组，不要其他内容：'
                        continue
                    else:
                        self._append_debug('多次环路分析返回为空，使用默认值。')
                        parsed = []
                        break
                
                try:
                    parsed = json.loads(result.strip())
                    if isinstance(parsed, list):
                        break
                    else:
                        raise ValueError("返回内容不是有效的JSON数组")
                except (json.JSONDecodeError, ValueError) as e:
                    if attempt < max_retries:
                        self._append_debug(f'第{attempt+1}次环路分析解析失败({e})，重新调用。')
                        system_prompt = f'你上次返回的内容不是有效的JSON格式：{result.strip()}\n\n请重新输出正确的JSON数组格式。\n\n只输出JSON数组，不要其他内容：'
                        continue
                    else:
                        self._append_debug(f'多次环路分析解析失败({e})，使用默认值。')
                        parsed = []
                        break
            
            speed_signals = [
                "rotor_angle_rad",
                "rotor_speed_rad_s",
                "electromagnetic_torque_nm"
            ]
            current_signals = [
                "stator_iq_a",
                "stator_id_a"
            ]
            
            available_signals = []
            if 'mechanical' in parsed:
                available_signals.extend(speed_signals)
            if 'current' in parsed:
                available_signals.extend(current_signals)
            
            data['available_signals'] = available_signals
            data['signals'] = {sig: sig for sig in available_signals}

            with open(project_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            self._append_error('信号和目标事件生成失败。', str(exc))

    # ── 用户可编辑字段：下次生成时从旧 metrics 中保留 ──
    _PRESERVABLE_FIELDS = (
        'target_value', 'good_threshold', 'bad_threshold',
        'weight', 'tolerance_ratio', 'window', 'normalize',
    )

    @staticmethod
    def _normalize_metric_item(item):
        """兼容旧格式（字符串）和新格式（含 constraints 的对象）。"""
        if isinstance(item, str):
            return item, []
        if isinstance(item, dict):
            return item.get('combo', ''), item.get('constraints') or []
        return '', []

    def _get_reference_target(self, signal_name, existing_metrics, existing_targets):
        """获取某个信号的参考目标值，用于百分比→绝对值的确定性转换。

        优先级：已有 targets > 已有 metrics > PHYSICAL_QUANTITIES 默认值。
        """
        if isinstance(existing_targets, dict):
            tv = existing_targets.get(signal_name)
            if isinstance(tv, dict):
                val = tv.get('target_value')
                if isinstance(val, (int, float)) and val != 0:
                    return float(val)
            elif isinstance(tv, (int, float)) and tv != 0:
                return float(tv)

        for m in (existing_metrics or []):
            if isinstance(m, dict) and m.get('signal') == signal_name:
                val = m.get('target_value')
                if isinstance(val, (int, float)) and val != 0:
                    return float(val)

        for phys_info in self.PHYSICAL_QUANTITIES.values():
            if phys_info.get('signal') == signal_name:
                return float(phys_info.get('target_value', 0.0))
        return 0.0

    # ── 正则模式：从自然语言中确定性提取目标转速 ──
    # .*? 非贪婪匹配关键字与数字之间的任意字符（如"速度目标是10rad/s"中的"目标是"）
    _TARGET_SPEED_PATTERNS = [
        # rpm 关键字在前：  "转速 1000rpm" / "目标转速改成 2000rpm" / "额定转速3000RPM"
        (r'(?:转速|目标转速|速度|额定转速).*?(\d+(?:\.\d+)?)\s*[rR][pP][mM]', 'rpm'),
        # rpm 数字在前：    "1000rpm 转速" / "3000 RPM"
        (r'(\d+(?:\.\d+)?)\s*[rR][pP][mM]', 'rpm'),
        # rad/s 关键字在前："目标转速 10rad/s" / "速度目标是10rad/s" / "转速改成 104.72 rad/s"
        (r'(?:转速|目标转速|速度|额定转速).*?(\d+(?:\.\d+)?)\s*rad/s', 'rad_s'),
        # rad/s 数字在前：  "10rad/s 的目标转速" / "104.72 rad/s"
        (r'(\d+(?:\.\d+)?)\s*rad/s', 'rad_s'),
    ]

    @classmethod
    def _extract_target_speed_from_text(cls, text):
        """从 objective 文本中确定性提取目标转速（rad/s）。

        优先级高于 LLM 约束提取，因为 LLM 可能遗漏或错误附加 combo。
        返回 None 表示未能识别。
        """
        import re
        for pattern, unit in cls._TARGET_SPEED_PATTERNS:
            match = re.search(pattern, str(text), re.IGNORECASE)
            if match:
                value = float(match.group(1))
                if unit == 'rpm':
                    return value * math.pi / 30.0
                return value
        return None

    def _collect_signal_targets(self, parsed_items, existing_metrics, existing_targets,
                                objective_text='', user_input=''):
        """从 LLM 输出 + objective 文本 + 用户原始输入中聚合信号级目标值覆盖。

        目标值（转速等）是信号级属性，同一个信号的所有 metric
        应该共享相同的 target_value。

        优先级：
        1. 用户原始输入正则提取（最高优先，用户说了算）
        2. objective 文本正则提取（LLM 整合后的文本）
        3. LLM constraints 中的 target_rpm / target_rad_s

        Returns:
            dict[str, float]: {signal_name: target_value}
        """
        collected = {}

        # 第一优先：从用户原始输入确定性提取（用户意图的最终权威来源）
        speed_target = self._extract_target_speed_from_text(user_input)
        if speed_target is None:
            # 回退：从 objective 文本提取
            speed_target = self._extract_target_speed_from_text(objective_text)
        if speed_target is not None and speed_target > 0:
            collected['rotor_speed_rad_s'] = speed_target

        # 标记已由正则确定的信号，LLM constraints 不得覆盖
        _regex_signals = set(collected.keys())

        # 第三优先：从 LLM constraints 补充（仅填充正则未覆盖的信号）
        for item in parsed_items:
            combo, constraints = self._normalize_metric_item(item)
            if not combo:
                continue
            parts = combo.split('_', 1)
            if len(parts) != 2:
                continue
            physical_quantity = parts[0].strip().lower()
            if physical_quantity not in self.PHYSICAL_QUANTITIES:
                continue
            signal_name = self.PHYSICAL_QUANTITIES[physical_quantity]["signal"]

            for c in (constraints or []):
                if not isinstance(c, dict):
                    continue
                ctype = str(c.get('type', '')).strip()
                try:
                    value = float(c.get('value', 0))
                except (TypeError, ValueError):
                    continue

                # 正则已确定的信号不受 LLM 约束覆盖
                if signal_name in _regex_signals:
                    continue

                if ctype == 'target_rpm':
                    collected[signal_name] = value * math.pi / 30.0
                elif ctype == 'target_rad_s':
                    collected[signal_name] = value

        return collected

    def _apply_constraints(self, constraints, signal_name, existing_metrics, existing_targets,
                           signal_target_overrides=None):
        """将 LLM 提取的约束转换为 metric 字段覆盖值。

        LLM 只负责从用户原文中提取数值和类型，Python 负责所有数学转换。
        返回 dict[str, float]，可直接 update 到 metric 对象上。

        signal_target_overrides: 预计算好的 {signal_name: target_value}，优先于
            _get_reference_target 的查询结果，确保百分比转换使用用户最新指定的目标值。
        """
        if not constraints:
            return {}
        overrides = {}
        ref_target = None  # 惰性计算

        for c in constraints:
            if not isinstance(c, dict):
                continue
            ctype = str(c.get('type', '')).strip()
            try:
                value = float(c.get('value', 0))
            except (TypeError, ValueError):
                continue

            if ctype == 'overshoot_percent':
                overrides['good_threshold'] = value / 100.0

            elif ctype == 'time_seconds':
                overrides['good_threshold'] = value

            elif ctype in ('error_absolute', 'ripple_absolute'):
                overrides['good_threshold'] = value

            elif ctype in ('error_percent', 'ripple_percent'):
                if ref_target is None:
                    # 优先使用 LLM 提取的目标值，否则走查询链
                    if isinstance(signal_target_overrides, dict) and signal_name in signal_target_overrides:
                        ref_target = signal_target_overrides[signal_name]
                    else:
                        ref_target = self._get_reference_target(
                            signal_name, existing_metrics, existing_targets,
                        )
                if ref_target and ref_target != 0:
                    overrides['good_threshold'] = value / 100.0 * abs(ref_target)
                    if 'bad_threshold' not in overrides and overrides['good_threshold'] > 0:
                        overrides['bad_threshold'] = overrides['good_threshold'] * 5.0

            # target_* 约束不在此处处理——由 _collect_signal_targets 预先聚合

        return overrides

    def _generate_metrics(self):
        project_json = self._project_json_path()
        if not project_json:
            return
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            objective_text = data.get('objective_text', '')
            objective = data.get('objective', '')
            available_signals = data.get('available_signals', [])

            if not objective_text.strip() and not objective.strip():
                data['metrics'] = []
                with open(project_json, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                return

            # ── 建立旧 metrics 索引，用于保留用户手动修改过的值 ──
            existing_metrics = data.get('metrics') or []
            existing_by_name = {}
            for m in existing_metrics:
                name = m.get('result_name', '') if isinstance(m, dict) else ''
                if name:
                    existing_by_name[name] = m
            existing_targets = data.get('targets') or {}

            # ── LLM 调用：提取 combo + 约束 ──
            system_prompt = (
                '你是性能评价指标分析助手。请根据用户需求文本，分析需要测量哪些物理量，'
                '以及用户明确给出了哪些数值要求。\n\n'
                '可选物理量：speed(速度), torque(转矩), iq(q轴电流), id(d轴电流)\n'
                '可选测量参数：overshoot(超调量), settling_time(调整时间), '
                'steady_state_error(稳态误差), ripple(纹波), rise_time(上升时间)\n\n'
                '约束类型（constraint type）说明：\n'
                '- overshoot_percent：超调百分比，value 为百分数（如用户说"超调小于5%"→value=5）\n'
                '- time_seconds：调节时间/上升时间秒数，value 为秒（如用户说"上升时间小于0.3s"→value=0.3）\n'
                '- error_absolute：稳态误差绝对值，value 为 rad/s 或 N*m 或 A\n'
                '- error_percent：稳态误差百分比，value 为百分数（如"稳态误差小于2%"→value=2）\n'
                '- ripple_absolute：纹波绝对值\n'
                '- ripple_percent：纹波百分比，value 为百分数\n'
                '- target_rpm：目标转速(rpm)，value 为 rpm 数值\n'
                '- target_rad_s：目标转速(rad/s)，value 为 rad/s 数值\n\n'
                '重要原则：\n'
                '- constraints 中每个值必须能直接从用户原文中找到，不要猜测或推算\n'
                '- 如果用户只说"响应快""低噪音"等定性描述没有具体数字，不要加 constraint\n'
                '- 如果某个 combo 没有任何用户明确给出的数值约束，constraints 可为空数组 []\n'
                '- 【关键】target_rpm / target_rad_s 是信号级约束，不是某个指标的专属参数。'
                '请将其作为 constraint 附加到该信号的任意一个 combo 上'
                '（例如 speed_overshoot），系统会自动同步到同信号的所有指标。'
                '不要因为"不知道该放哪个 combo"而遗漏目标转速约束。\n\n'
                '输出格式（严格遵守）：只输出 JSON 数组，每个元素格式：\n'
                '{"combo": "物理量_测量参数", '
                '"constraints": [{"type": "约束类型", "value": 数值}]}\n'
                '示例：\n'
                '[{"combo": "speed_overshoot", '
                '"constraints": [{"type": "overshoot_percent", "value": 5}, '
                '{"type": "target_rad_s", "value": 104.72}]},'
                ' {"combo": "speed_settling_time", '
                '"constraints": [{"type": "time_seconds", "value": 0.5}]},'
                ' {"combo": "speed_steady_state_error", '
                '"constraints": [{"type": "error_percent", "value": 2}]}]\n\n'
                '用户需求：' + objective + '\n\n'
                '请输出JSON数组：'
            )

            parsed = None
            max_retries = 2
            for attempt in range(max_retries + 1):
                result = call_ui_chat_model(objective, system_prompt, temperature=0.2)
                self._append_debug(f'大模型返回（评价指标分析）：{result.strip()}')

                if not result or not result.strip():
                    if attempt < max_retries:
                        self._append_debug(f'第{attempt+1}次评价指标分析返回为空，重新调用。')
                        system_prompt = '你上次返回了空内容。请重新输出正确的JSON数组格式。\n\n只输出JSON数组，不要其他内容：'
                        continue
                    self._append_debug('多次评价指标分析返回为空，使用默认指标。')
                    parsed = [
                        {"combo": "speed_overshoot", "constraints": []},
                        {"combo": "speed_settling_time", "constraints": []},
                        {"combo": "speed_steady_state_error", "constraints": []},
                    ]
                    break

                try:
                    parsed = json.loads(result.strip())
                    if isinstance(parsed, list) and len(parsed) > 0:
                        break
                    raise ValueError("返回内容不是有效的JSON数组或数组为空")
                except (json.JSONDecodeError, ValueError) as e:
                    if attempt < max_retries:
                        self._append_debug(f'第{attempt+1}次评价指标分析解析失败({e})，重新调用。')
                        system_prompt = (
                            f'你上次返回的内容不是有效的JSON格式：{result.strip()}\n\n'
                            '请重新输出正确的JSON数组格式。\n\n只输出JSON数组，不要其他内容：'
                        )
                        continue
                    self._append_debug(f'多次评价指标分析解析失败({e})，使用默认指标。')
                    parsed = [
                        {"combo": "speed_overshoot", "constraints": []},
                        {"combo": "speed_settling_time", "constraints": []},
                        {"combo": "speed_steady_state_error", "constraints": []},
                    ]
                    break

            # ── 预处理：聚合信号级目标值覆盖 ──
            signal_target_overrides = self._collect_signal_targets(
                parsed, existing_metrics, existing_targets,
                objective_text=objective,
                user_input=self._last_user_input or '',
            )

            # ── 构建 metrics：模板默认 → 旧值保留 → 信号级目标值覆盖 → LLM 约束覆盖 ──
            metrics = []
            for item in parsed:
                combo, constraints = self._normalize_metric_item(item)
                if not combo:
                    continue

                parts = combo.split('_', 1)
                if len(parts) != 2:
                    continue
                physical_quantity = parts[0].strip().lower()
                metric_param = parts[1].strip().lower()

                if physical_quantity not in self.PHYSICAL_QUANTITIES:
                    continue
                if metric_param not in self.METRICS_PARAM_TEMPLATES:
                    continue

                phys_info = self.PHYSICAL_QUANTITIES[physical_quantity]
                param_template = self.METRICS_PARAM_TEMPLATES[metric_param]
                signal_name = phys_info["signal"]

                if available_signals and signal_name not in available_signals:
                    continue

                # 第一层：模板默认值
                metric = {
                    "result_name": combo,
                    "signal": signal_name,
                    "target_value": phys_info["target_value"],
                    "weight": phys_info["weight"],
                }
                metric.update(param_template)

                # 第二层：保留用户手动修改过的旧值
                if combo in existing_by_name:
                    old = existing_by_name[combo]
                    for field in self._PRESERVABLE_FIELDS:
                        if field in old:
                            metric[field] = old[field]

                # 第三层：信号级目标值覆盖（正则/LM 提取的 target_rpm / target_rad_s）
                # 同一信号的所有 metric 共享此值，且优先级高于旧值保留
                if signal_name in signal_target_overrides:
                    metric['target_value'] = signal_target_overrides[signal_name]

                # 第四层：LLM 约束覆盖（非 target 类约束）
                # 使用 signal_target_overrides 作为参考目标值，
                # 确保 error_percent 等百分比转换使用用户最新指定的目标值
                constraint_overrides = self._apply_constraints(
                    constraints, signal_name, existing_metrics, existing_targets,
                    signal_target_overrides=signal_target_overrides,
                )
                metric.update(constraint_overrides)

                metrics.append(metric)

            data['metrics'] = metrics
            with open(project_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            self._append_error('评价指标生成失败。', str(exc))

    def _generate_targets_from_metrics(self):
        project_json = self._project_json_path()
        if not project_json:
            return
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            metrics = data.get('metrics', [])
            if not metrics:
                return
            
            signals_needed = set()
            for metric in metrics:
                signal = metric.get('signal')
                if signal:
                    signals_needed.add(signal)
            
            signal_info = {
                "rotor_speed_rad_s": {"unit": "rad/s", "description": "期望稳定转速"},
                "electromagnetic_torque_nm": {"unit": "N*m", "description": "期望稳定转矩"},
                "stator_iq_a": {"unit": "A", "description": "期望 q 轴电流"},
                "stator_id_a": {"unit": "A", "description": "期望 d 轴电流"}
            }
            
            targets = {}
            for signal in signals_needed:
                if signal in signal_info:
                    target_value = 0.0
                    for metric in metrics:
                        if metric.get('signal') == signal:
                            target_value = metric.get('target_value', 0.0)
                            break
                    
                    targets[signal] = {
                        "target_value": target_value,
                        "unit": signal_info[signal]["unit"],
                        "description": signal_info[signal]["description"]
                    }
            
            data['targets'] = targets
            with open(project_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self._update_param_table(targets)

            # 同步目标转速到 ctl_main.c 的速度环设定值
            if 'rotor_speed_rad_s' in targets:
                speed_target = targets['rotor_speed_rad_s'].get('target_value', 0.0)
                self._append_debug(
                    f'_generate_targets_from_metrics: 检测到速度目标值={speed_target} rad/s，'
                    f'准备同步到 ctl_main.c'
                )
                if speed_target > 0:
                    self._update_ctl_main_target_velocity(speed_target)
            else:
                self._append_debug(
                    '_generate_targets_from_metrics: rotor_speed_rad_s 不在 targets 中，'
                    f'当前 targets 键: {list(targets.keys())}'
                )
        except Exception as exc:
            self._append_error('目标参数生成失败。', str(exc))

    def _update_param_table(self, targets):
        self.param_table.setRowCount(len(targets))
        row = 0
        for signal, target_info in targets.items():
            signal_item = QTableWidgetItem(signal)
            signal_item.setFlags(signal_item.flags() & ~Qt.ItemIsEditable)
            
            target_value_item = QTableWidgetItem(str(target_info.get('target_value', 0.0)))
            target_value_item.setData(Qt.UserRole, signal)
            
            unit_item = QTableWidgetItem(target_info.get('unit', ''))
            unit_item.setFlags(unit_item.flags() & ~Qt.ItemIsEditable)
            
            self.param_table.setItem(row, 0, signal_item)
            self.param_table.setItem(row, 1, target_value_item)
            self.param_table.setItem(row, 2, unit_item)
            row += 1
        
        self.param_table.itemChanged.connect(self._on_target_value_changed)

    def _on_target_value_changed(self, item):
        if item.column() != 1:
            return
        
        signal = item.data(Qt.UserRole)
        if not signal:
            return
        
        try:
            new_value = float(item.text())
        except ValueError:
            QMessageBox.warning(self, '提示', '请输入有效的数字')
            item.setText(str(self._get_current_target_value(signal)))
            return
        
        self._sync_target_value(signal, new_value)

    def _get_current_target_value(self, signal):
        project_json = self._project_json_path()
        if not project_json:
            return 0.0
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            targets = data.get('targets', {})
            return targets.get(signal, {}).get('target_value', 0.0)
        except Exception:
            return 0.0

    def _sync_target_value(self, signal, new_value):
        project_json = self._project_json_path()
        if not project_json:
            return
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if 'targets' in data and signal in data['targets']:
                data['targets'][signal]['target_value'] = new_value
            
            if 'metrics' in data:
                for metric in data['metrics']:
                    if metric.get('signal') == signal:
                        metric['target_value'] = new_value
            
            with open(project_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            if signal == 'rotor_speed_rad_s':
                self._update_ctl_main_target_velocity(new_value)
        except Exception as exc:
            self._append_error('目标值同步失败。', str(exc))

    def _update_ctl_main_target_velocity(self, target_speed):
        ctl_main_paths = self._ctl_main_paths()
        if not ctl_main_paths:
            return
        try:
            updated_paths = []
            for ctl_main_path in ctl_main_paths:
                with open(ctl_main_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                updated_content, changed = self._rewrite_target_velocity_literal(content, target_speed)
                if not changed:
                    continue

                with open(ctl_main_path, 'w', encoding='utf-8') as f:
                    f.write(updated_content)
                updated_paths.append(ctl_main_path)

            if updated_paths:
                names = ', '.join(path.name for path in updated_paths)
                self._append_success(f'目标速度已同步到 {names}。')
            else:
                self._append_notice('未找到可更新的 ctl_main.c 目标速度行。')
        except Exception as exc:
            self._append_error('更新 ctl_main.c 目标速度失败。', str(exc))

    def _generate_stop_conditions(self):
        project_json = self._project_json_path()
        if not project_json:
            return
        try:
            with open(project_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            data['stop_conditions'] = {
                'overall_score_min': 85,
                'metric_error_count_max': 0
            }
            with open(project_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            self._append_error('停止条件生成失败。', str(exc))

    def on_chat_failure(self, error_text: str):
        self.chat_view.hide_thinking()
        self._append_error('对话失败，请检查设置与网络。', error_text)
        self._set_status_text('状态：对话失败，请检查设置与网络')

    def on_chat_finished(self):
        self.chat_view.hide_thinking()
        self.send_btn.setEnabled(True)
        if callable(self.external_finished_callback):
            self.external_finished_callback()
