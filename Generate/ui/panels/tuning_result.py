from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PyQt5.QtCore import QFileSystemWatcher
from PyQt5.QtCore import Qt
import json
from pathlib import Path

from widgets.chat import TranslationWorker
from styles.theme import current_theme, ghost_button_qss


class TuningResultPanel(QWidget):
    def __init__(self, project_json_getter=None, parent=None):
        super().__init__(parent)
        self.project_json_getter = project_json_getter
        self._current_result_key = ''
        self._current_summary_key = ''
        self._translated_summary = ''
        self._current_score = None
        self._current_summary_text = ''
        self._competition_details_data = {}
        self._translation_worker = None
        self._pending_refresh = False
        self._last_source_path = ''
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._on_watch_triggered)
        self._watcher.directoryChanged.connect(self._on_watch_triggered)
        self._watched_paths = set()
        t = current_theme()
        self.setObjectName('tuningResultPanel')
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f'QWidget#tuningResultPanel{{background:{t.panel};border:none;}}')

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_row = QWidget()
        title_row.setAttribute(Qt.WA_StyledBackground, True)
        title_row.setStyleSheet(f'background:{t.panel};border:none;')
        title_layout = QHBoxLayout(title_row)
        title_layout.setContentsMargins(8, 4, 8, 4)
        title_label = QLabel('调优结果')
        title_label.setStyleSheet(f'font-size:14px;font-weight:600;color:{t.muted};')
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        refresh_btn = QPushButton('刷新结果')
        refresh_btn.setStyleSheet(ghost_button_qss(padding='4px 10px'))
        refresh_btn.clicked.connect(self.refresh_from_project)
        title_layout.addWidget(refresh_btn)

        self.result_scroll = QScrollArea()
        self.result_scroll.setWidgetResizable(True)
        self.result_scroll.setFrameShape(QFrame.NoFrame)
        self.result_scroll.setStyleSheet(
            f'QScrollArea{{background:{t.panel};border:none;}}'
            f'QScrollArea > QWidget > QWidget{{background:{t.panel};}}'
        )

        result_body = QWidget()
        result_body.setStyleSheet(f'background:{t.panel};border:none;')
        result_layout = QVBoxLayout(result_body)
        result_layout.setContentsMargins(8, 8, 8, 8)
        result_layout.setSpacing(8)

        self.score_card = QFrame()
        self.score_card.setObjectName('scoreCard')
        self.score_card.setStyleSheet(self._card_qss('scoreCard'))
        score_layout = QHBoxLayout(self.score_card)
        score_layout.setContentsMargins(12, 10, 12, 10)
        score_text_layout = QVBoxLayout()
        score_text_layout.setSpacing(2)
        score_caption = QLabel('综合评分')
        score_caption.setStyleSheet(f'font-size:12px;color:{t.muted};')
        score_text_layout.addWidget(score_caption)
        score_value_row = QHBoxLayout()
        score_value_row.setSpacing(4)
        self.score_label = QLabel('—')
        self.score_label.setStyleSheet(f'font-size:28px;font-weight:700;color:{t.text_strong};')
        score_value_row.addWidget(self.score_label)
        score_unit = QLabel('/ 100')
        score_unit.setStyleSheet(f'font-size:12px;color:{t.muted};padding-top:10px;')
        score_value_row.addWidget(score_unit)
        score_value_row.addStretch()
        score_text_layout.addLayout(score_value_row)
        score_layout.addLayout(score_text_layout, 1)
        self.status_badge = QLabel()
        self.status_badge.setAlignment(Qt.AlignCenter)
        self.status_badge.hide()
        score_layout.addWidget(self.status_badge, 0, Qt.AlignTop)
        result_layout.addWidget(self.score_card)

        self.summary_card = QFrame()
        self.summary_card.setObjectName('summaryCard')
        self.summary_card.setStyleSheet(self._card_qss('summaryCard'))
        summary_layout = QVBoxLayout(self.summary_card)
        summary_layout.setContentsMargins(12, 10, 12, 12)
        summary_layout.setSpacing(8)
        summary_title = QLabel('结果摘要')
        summary_title.setStyleSheet(f'font-size:12px;font-weight:600;color:{t.text_strong};')
        summary_layout.addWidget(summary_title)
        self.summary_label = QLabel('等待生成调优结果…')
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.summary_label.setStyleSheet(f'font-size:13px;color:{t.text};line-height:1.6;')
        summary_layout.addWidget(self.summary_label)
        self.reason_title = QLabel('胜出原因')
        self.reason_title.setStyleSheet(f'font-size:12px;font-weight:600;color:{t.muted};padding-top:4px;')
        self.reason_label = QLabel()
        self.reason_label.setWordWrap(True)
        self.reason_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.reason_label.setStyleSheet(f'font-size:13px;color:{t.text};')
        summary_layout.addWidget(self.reason_title)
        summary_layout.addWidget(self.reason_label)
        self.reason_title.hide()
        self.reason_label.hide()
        result_layout.addWidget(self.summary_card)

        self.candidates_card = QFrame()
        self.candidates_card.setObjectName('candidatesCard')
        self.candidates_card.setStyleSheet(self._card_qss('candidatesCard'))
        candidates_layout = QVBoxLayout(self.candidates_card)
        candidates_layout.setContentsMargins(12, 10, 12, 12)
        candidates_layout.setSpacing(8)
        candidates_title = QLabel('候选方案')
        candidates_title.setStyleSheet(f'font-size:12px;font-weight:600;color:{t.text_strong};')
        candidates_layout.addWidget(candidates_title)
        self.candidates_table = QTableWidget(0, 4)
        self.candidates_table.setHorizontalHeaderLabels(('方案', '得分', '状态', '停止原因'))
        self.candidates_table.verticalHeader().hide()
        self.candidates_table.setShowGrid(False)
        self.candidates_table.setAlternatingRowColors(True)
        self.candidates_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.candidates_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.candidates_table.setFocusPolicy(Qt.NoFocus)
        self.candidates_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.candidates_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.candidates_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.candidates_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.candidates_table.setStyleSheet(
            f'QTableWidget{{background:{t.surface};alternate-background-color:{t.panel};border:none;'
            f'color:{t.text};font-size:12px;}}'
            f'QHeaderView::section{{background:{t.panel};color:{t.muted};border:none;'
            f'border-bottom:1px solid {t.border};padding:5px 6px;font-weight:600;}}'
            f'QTableWidget::item{{border:none;padding:4px 6px;}}'
        )
        candidates_layout.addWidget(self.candidates_table)
        self.candidates_card.hide()
        result_layout.addWidget(self.candidates_card)
        result_layout.addStretch()
        self.result_scroll.setWidget(result_body)

        self.source_label = QLabel('来源：未加载项目')
        self.source_label.setStyleSheet(
            f'font-size:11px;color:{t.subtle};background:{t.panel};border:none;padding:4px 8px 8px 8px;'
        )
        self.source_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        layout.addWidget(title_row)
        layout.addWidget(self.result_scroll, 1)
        layout.addWidget(self.source_label)

        self.refresh_from_project()

    @staticmethod
    def _card_qss(object_name):
        t = current_theme()
        return (
            f'QFrame#{object_name}{{background:{t.surface};border:1px solid {t.border};border-radius:8px;}}'
            f'QFrame#{object_name} QLabel{{background:transparent;border:none;}}'
        )

    def _project_json_path(self):
        if callable(self.project_json_getter):
            return self.project_json_getter()
        return None

    @staticmethod
    def _normalize_summary(summary):
        if summary is None:
            return ''
        if isinstance(summary, str):
            return summary.strip()
        if isinstance(summary, (list, tuple)):
            parts = []
            for item in summary:
                if isinstance(item, str):
                    text = item.strip()
                else:
                    text = json.dumps(item, ensure_ascii=False, indent=2)
                if text:
                    parts.append(text)
            return '\n'.join(parts).strip()
        if isinstance(summary, dict):
            return json.dumps(summary, ensure_ascii=False, indent=2).strip()
        return str(summary).strip()

    def _result_summary_text(self, payload):
        if not isinstance(payload, dict):
            return ''
        rounds = payload.get('rounds')
        if isinstance(rounds, list):
            for item in reversed(rounds):
                if not isinstance(item, dict):
                    continue
                text = self._normalize_summary(item.get('assistant_summary'))
                if text:
                    return text
        return self._normalize_summary(payload.get('setup_summary'))

    @staticmethod
    def _format_score(value):
        if value is None:
            return '—'
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    def _tuning_result_path(self):
        project_json = self._project_json_path()
        if not project_json:
            return None
        try:
            return Path(project_json).parent / 'tuning_result.json'
        except Exception:
            return None

    def _project_dir(self):
        project_json = self._project_json_path()
        if not project_json:
            return None
        try:
            return Path(project_json).parent
        except Exception:
            return None

    @staticmethod
    def _read_json(path: Path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _competition_result_path(self):
        project_dir = self._project_dir()
        if project_dir is None:
            return None
        for name in ('competition_run_result.json', 'competition_dry_run_result.json'):
            path = project_dir / name
            if path.exists():
                return path
        return None

    @staticmethod
    def _competition_details(competition_payload):
        if not isinstance(competition_payload, dict):
            return {}
        scoreboard = competition_payload.get('scoreboard')
        winner = competition_payload.get('winner')
        return {
            'winner_reason': str(competition_payload.get('winner_reason') or '').strip(),
            'requirement_satisfied': competition_payload.get('requirement_satisfied'),
            'scoreboard': [item for item in scoreboard if isinstance(item, dict)] if isinstance(scoreboard, list) else [],
            'winner_id': str(winner.get('candidate_id') or '') if isinstance(winner, dict) else '',
        }

    def _candidate_result_from_competition(self, competition_payload):
        if not isinstance(competition_payload, dict):
            return None

        winner = competition_payload.get('winner')
        if isinstance(winner, dict):
            winner_path = winner.get('tuning_result')
            if winner_path:
                path = Path(str(winner_path))
                if path.exists():
                    return path

        scoreboard = competition_payload.get('scoreboard')
        if isinstance(scoreboard, list):
            scored_items = []
            fallback_items = []
            for item in scoreboard:
                if not isinstance(item, dict):
                    continue
                path_text = item.get('tuning_result')
                if not path_text:
                    continue
                path = Path(str(path_text))
                if not path.exists():
                    continue
                score = item.get('overall_score')
                if isinstance(score, (int, float)):
                    scored_items.append((float(score), path))
                else:
                    fallback_items.append(path)
            if scored_items:
                scored_items.sort(key=lambda pair: pair[0], reverse=True)
                return scored_items[0][1]
            if fallback_items:
                return fallback_items[0]

        optimize_items = competition_payload.get('optimize')
        if isinstance(optimize_items, list):
            for item in optimize_items:
                if not isinstance(item, dict):
                    continue
                outputs = item.get('outputs')
                if not isinstance(outputs, dict):
                    continue
                path_text = outputs.get('tuning_result')
                if path_text:
                    path = Path(str(path_text))
                    if path.exists():
                        return path
        return None

    def _resolve_result_source(self):
        root_result = self._tuning_result_path()
        if root_result is not None and root_result.exists():
            return root_result, None

        competition_path = self._competition_result_path()
        if competition_path is None:
            return None, None

        try:
            competition_payload = self._read_json(competition_path)
        except Exception:
            return None, None

        candidate_result = self._candidate_result_from_competition(competition_payload)
        return candidate_result, competition_payload

    def _clear_watch_paths(self):
        paths = list(self._watched_paths)
        if paths:
            try:
                self._watcher.removePaths(paths)
            except Exception:
                pass
        self._watched_paths.clear()

    def _set_watch_path(self, path: Path | None):
        if path is None:
            return
        path_text = str(path)
        if path_text not in self._watched_paths and path.exists():
            try:
                if self._watcher.addPath(path_text):
                    self._watched_paths.add(path_text)
            except Exception:
                pass

    def _sync_watch_paths(self):
        tuning_result_path = self._tuning_result_path()
        competition_result_path = self._competition_result_path()
        competition_candidate_result_path = None
        project_json = self._project_json_path()
        project_dir = None
        if project_json:
            try:
                project_dir = Path(project_json).parent
            except Exception:
                project_dir = None

        desired_paths = set()
        if project_dir is not None:
            desired_paths.add(str(project_dir))
        if tuning_result_path is not None and tuning_result_path.exists():
            desired_paths.add(str(tuning_result_path))
        if competition_result_path is not None and competition_result_path.exists():
            desired_paths.add(str(competition_result_path))
            try:
                competition_payload = self._read_json(competition_result_path)
                candidate_result = self._candidate_result_from_competition(competition_payload)
                if candidate_result is not None and candidate_result.exists():
                    competition_candidate_result_path = candidate_result
                    desired_paths.add(str(candidate_result))
            except Exception:
                pass

        current_paths = set(self._watched_paths)
        to_remove = list(current_paths - desired_paths)
        if to_remove:
            try:
                self._watcher.removePaths(to_remove)
            except Exception:
                pass
            for path_text in to_remove:
                self._watched_paths.discard(path_text)

        if project_dir is not None:
            self._set_watch_path(project_dir)
        if tuning_result_path is not None and tuning_result_path.exists():
            self._set_watch_path(tuning_result_path)
        if competition_result_path is not None and competition_result_path.exists():
            self._set_watch_path(competition_result_path)
        if competition_candidate_result_path is not None and competition_candidate_result_path.exists():
            self._set_watch_path(competition_candidate_result_path)

    def _on_watch_triggered(self, _path: str):
        self.refresh_from_project()

    def _set_status_badge(self, text, kind='neutral'):
        t = current_theme()
        palettes = {
            'success': (t.success_bg, t.success_border, t.success_text),
            'error': (t.error_bg, t.error_border, t.error_text),
            'neutral': (t.primary_soft, t.primary_border, t.primary_text),
        }
        background, border, color = palettes.get(kind, palettes['neutral'])
        self.status_badge.setText(text)
        self.status_badge.setStyleSheet(
            f'font-size:11px;font-weight:600;color:{color};background:{background};'
            f'border:1px solid {border};border-radius:9px;padding:3px 8px;'
        )
        self.status_badge.show()

    def _hide_status_badge(self):
        self.status_badge.clear()
        self.status_badge.hide()

    @staticmethod
    def _display_status(value):
        text = str(value or '').strip()
        aliases = {
            'completed': '已完成',
            'complete': '已完成',
            'success': '成功',
            'succeeded': '成功',
            'failed': '失败',
            'error': '异常',
            'running': '运行中',
            'pending': '等待中',
            'skipped': '已跳过',
            'stopped': '已停止',
        }
        return aliases.get(text.lower(), text or '—')

    @staticmethod
    def _display_stop_reason(value):
        text = str(value or '').strip()
        aliases = {
            'requirement_satisfied': '已满足需求',
            'max_iterations': '达到最大迭代次数',
            'completed': '正常完成',
            'failed': '运行失败',
            'cancelled': '已取消',
            'canceled': '已取消',
            'timeout': '运行超时',
        }
        return aliases.get(text.lower(), text or '—')

    def _populate_candidates(self, details):
        scoreboard = details.get('scoreboard') if isinstance(details, dict) else []
        scoreboard = scoreboard if isinstance(scoreboard, list) else []
        self.candidates_table.setRowCount(len(scoreboard))
        winner_id = str(details.get('winner_id') or '') if isinstance(details, dict) else ''
        t = current_theme()
        for row, item in enumerate(scoreboard):
            candidate_id = str(item.get('candidate_id') or '—')
            is_winner = bool(winner_id and candidate_id == winner_id)
            values = (
                f'{candidate_id}（最佳）' if is_winner else candidate_id,
                self._format_score(item.get('overall_score')),
                self._display_status(item.get('status')),
                self._display_stop_reason(item.get('stop_reason')),
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setTextAlignment(Qt.AlignCenter)
                if is_winner:
                    cell.setBackground(QColor(t.primary_soft))
                    cell.setForeground(QColor(t.primary_text))
                self.candidates_table.setItem(row, column, cell)
            self.candidates_table.setRowHeight(row, 30)

        if scoreboard:
            table_height = self.candidates_table.horizontalHeader().height() + min(len(scoreboard), 4) * 30 + 2
            self.candidates_table.setFixedHeight(table_height)
            self.candidates_card.show()
        else:
            self.candidates_card.hide()

    def _render(self, score_value, translated_summary, source_path_text, status_text=None, competition_details=None):
        details = competition_details if isinstance(competition_details, dict) else {}
        self.score_label.setText(self._format_score(score_value))

        satisfied = details.get('requirement_satisfied')
        normalized_status = str(status_text or '')
        if '失败' in normalized_status or '异常' in normalized_status:
            self._hide_status_badge()
        elif satisfied is True:
            self._set_status_badge('满足需求', 'success')
        elif score_value is None:
            self._hide_status_badge()
        elif '正在翻译' in normalized_status:
            self._hide_status_badge()
        elif satisfied is False:
            self._set_status_badge('继续调优')
        else:
            self._set_status_badge('调优完成', 'success')

        body = (translated_summary or '').strip()
        if body:
            self.summary_label.setText(body)
        elif score_value is None:
            self.summary_label.setText('运行调优后，这里将显示评分、结果摘要和候选方案对比。')
        else:
            self.summary_label.setText('正在整理调优结果…')
        self.summary_card.setToolTip(normalized_status)

        reason = str(details.get('winner_reason') or '').strip()
        self.reason_label.setText(reason)
        self.reason_title.setVisible(bool(reason))
        self.reason_label.setVisible(bool(reason))
        self._populate_candidates(details)

        if source_path_text:
            source_path = Path(source_path_text)
            self.source_label.setText(f'来源：{source_path.name}')
            self.source_label.setToolTip(str(source_path))
        else:
            self.source_label.setText('来源：尚未生成 tuning_result.json')
            self.source_label.setToolTip('')

    def _start_translation(self, summary_key: str, summary_text: str):
        if self._translation_worker is not None and self._translation_worker.isRunning():
            self._pending_refresh = True
            return

        self._translation_worker = TranslationWorker(summary_key, summary_text, self)
        self._translation_worker.success.connect(self._on_translation_success)
        self._translation_worker.failure.connect(self._on_translation_failure)
        self._translation_worker.finished.connect(self._on_translation_finished)
        self._translation_worker.start()

    def _on_translation_success(self, summary_key: str, translated_text: str):
        if summary_key != self._current_summary_key:
            return
        self._translated_summary = translated_text.strip()
        self._render(
            self._current_score,
            self._translated_summary,
            self._last_source_path,
            '翻译完成',
            self._competition_details_data,
        )

    def _on_translation_failure(self, summary_key: str, error_text: str):
        if summary_key != self._current_summary_key:
            return
        fallback = self._current_summary_text or '翻译失败：' + error_text
        self._translated_summary = fallback
        self._render(
            self._current_score,
            self._translated_summary,
            self._last_source_path,
            f'翻译失败：{error_text}',
            self._competition_details_data,
        )

    def _on_translation_finished(self):
        self._translation_worker = None
        if self._pending_refresh:
            self._pending_refresh = False
            self.refresh_from_project()

    def refresh_from_project(self):
        self._sync_watch_paths()
        tuning_result_path, competition_payload = self._resolve_result_source()
        competition_details = self._competition_details(competition_payload)
        self._competition_details_data = competition_details
        if not tuning_result_path or not tuning_result_path.exists():
            self._current_result_key = ''
            self._current_summary_key = ''
            self._translated_summary = ''
            self._current_score = None
            self._current_summary_text = ''
            self._last_source_path = ''
            self._render(None, '', '', '未找到 tuning_result.json', competition_details)
            return

        try:
            with open(tuning_result_path, 'r', encoding='utf-8') as f:
                payload = json.load(f)
        except Exception as exc:
            self._render(None, f'读取失败：{exc}', str(tuning_result_path), f'读取 tuning_result.json 失败：{exc}', competition_details)
            return

        final_evaluation = payload.get('final_evaluation') or {}
        score_value = final_evaluation.get('overall_score')
        summary_text = self._result_summary_text(payload)
        details_key = json.dumps(competition_details, ensure_ascii=False, sort_keys=True, default=str)
        summary_key = f'{tuning_result_path}:{details_key}:{summary_text}'
        result_key = f'{tuning_result_path}:{score_value!r}:{summary_key}'

        self._last_source_path = str(tuning_result_path)
        score_changed = score_value != self._current_score
        summary_changed = summary_key != self._current_summary_key
        if result_key == self._current_result_key:
            return

        self._current_result_key = result_key
        self._current_score = score_value
        self._current_summary_text = summary_text

        if not summary_text:
            self._current_summary_key = ''
            self._translated_summary = ''
            self._render(score_value, '', str(tuning_result_path), '结果摘要为空', competition_details)
            return

        if summary_changed:
            self._current_summary_key = summary_key
            self._translated_summary = ''
            self._render(score_value, '正在整理结果摘要…', str(tuning_result_path), '正在翻译结果摘要', competition_details)
            self._start_translation(summary_key, summary_text)
        else:
            self._render(score_value, self._translated_summary, str(tuning_result_path), '综合评分已刷新' if score_changed else None, competition_details)
