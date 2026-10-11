"""Offline UI checks; the process-tree check kills only its own test processes."""
from contextlib import ExitStack, redirect_stdout
import ctypes
from ctypes import wintypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'Generate/ui'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5.QtCore import QThread
from PyQt5.QtGui import QMovie
from PyQt5.QtWidgets import QApplication
from panels.main_program import MainProgramPanel
from panels.requirement import RequirementPanel
from widgets.chat import ChatWorker
from core.paths import GENERATE_ROOT
from workflow.task_control import StopProcessWorker
from Optimize.agent_optimize.agent_core import app as agent_app
from Optimize.agent_optimize.agent_core.checkpoint import job_signature, load_checkpoint
from Optimize.agent_optimize.agent_core.config import ProjectContext
from Optimize.agent_optimize.agent_core.parameters.parameter_header_editor import _write_text, ParameterHeaderFileError
from Optimize.agent_silhelper import remote_sil_client
from Competition import competition_runner
from silworker.remote_sil_worker import SilWorkerState
from ui_main import MainWindow
import run_agent as legacy_launcher


class PauseResumeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def pump(self, predicate, timeout=4):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and not predicate():
            self.app.processEvents()
            time.sleep(0.01)
        self.app.processEvents()
        self.assertTrue(predicate())

    def test_send_button_stops_chat_preserves_draft_and_accepts_next_message(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / 'project.json'
            project.write_text('{}', encoding='utf-8')
            panel = MainProgramPanel(project_json_getter=lambda: str(project))
            entered = threading.Event()

            def chat(prompt, system):
                if prompt == 'old':
                    entered.set()
                    while not QThread.currentThread().isInterruptionRequested():
                        time.sleep(0.01)
                    return 'stale response'
                return 'new response'

            with patch('widgets.chat.call_ui_chat_model', side_effect=chat), \
                    patch('workflow.agent_flow.call_ui_chat_model', return_value='{"action":"answer_question"}'):
                panel._chat_task = 'answer'
                panel.chat_worker = ChatWorker('old', '', panel)
                panel.chat_worker.success.connect(panel.on_chat_success)
                panel.chat_worker.finished.connect(panel.on_chat_finished)
                panel.chat_worker.start()
                self.assertTrue(entered.wait(2))
                panel._sync_task_button()
                self.assertEqual(panel.send_btn.text(), '停止')
                self.assertTrue(panel.send_btn.isEnabled())
                panel.input_edit.setPlainText('draft to keep')
                panel.send_btn.click()
                self.pump(lambda: not panel.chat_worker.isRunning())
                panel._sync_task_button()
                self.assertEqual(panel.send_btn.text(), '发送')
                self.assertEqual(panel.input_edit.toPlainText(), 'draft to keep')
                self.assertFalse(any(x['text'] == 'stale response' for x in panel.chat_history))
                panel.input_edit.setPlainText('为什么响应比较慢？')
                panel.send_btn.click()
                self.pump(lambda: any(x['text'] == 'new response' for x in panel.chat_history))
                self.pump(lambda: not panel.chat_worker.isRunning())
            panel._task_button_timer.stop()
            panel.deleteLater()
            self.app.processEvents()

    def test_paused_tuning_resumes_by_chat(self):
        panel = MainProgramPanel()
        resumed = []
        panel.stop_tuning_callback = lambda: panel.set_tuning_active(False)
        panel.resume_tuning_callback = lambda: (resumed.append(True), panel.set_tuning_active(True))
        panel.set_tuning_active(True)
        panel.send_btn.click()
        panel.input_edit.setPlainText('继续运行')
        panel.send_btn.click()
        self.assertEqual(resumed, [True])
        self.assertEqual(panel.send_btn.text(), '停止')
        panel.set_tuning_active(False)
        panel._task_button_timer.stop()
        panel.deleteLater()
        self.app.processEvents()

    def test_background_status_reuses_waiting_animation_and_cleans_up(self):
        panel = MainProgramPanel()
        try:
            panel._set_status_text('状态：第 1 轮调优进行中')
            panel.set_tuning_active(True)
            indicator = panel.chat_view._thinking_widget
            self.assertIsNotNone(indicator)
            self.assertEqual(indicator.text_label.text(), '第 1 轮调优进行中')
            self.assertEqual(Path(indicator.movie.fileName()), GENERATE_ROOT / '旋转.gif')
            self.assertTrue(indicator.movie.isValid())
            self.assertEqual(indicator.movie.state(), QMovie.Running)
            initial_frame = indicator.movie.currentFrameNumber()
            self.pump(lambda: indicator.movie.currentFrameNumber() != initial_frame)
            panel._set_status_text('状态：candidate_01：仿真运行中')
            panel._sync_task_button()
            self.assertIs(panel.chat_view._thinking_widget, indicator)
            self.assertEqual(indicator.text_label.text(), 'candidate_01：仿真运行中')
            self.assertEqual(sum(row[0] == '__thinking__' for row in panel.chat_view.message_rows), 1)
            panel._stopping = True
            panel._sync_task_button()
            self.assertEqual(indicator.text_label.text(), '正在停止…')
            panel.set_tuning_active(False)
            self.assertIsNone(panel.chat_view._thinking_widget)
            self.assertEqual(indicator.movie.state(), QMovie.NotRunning)
        finally:
            panel.set_tuning_active(False)
            panel._task_button_timer.stop()
            panel.deleteLater()
            self.app.processEvents()

    def test_metric_pipeline_can_stop_before_subsequent_phases(self):
        panel = MainProgramPanel()
        requirement = RequirementPanel(parent=panel)
        panel.set_workflow_widgets(requirement_panel=requirement)
        entered = threading.Event()

        def task_type():
            entered.set()
            while not QThread.currentThread().isInterruptionRequested():
                time.sleep(0.01)

        with ExitStack() as stack:
            stack.enter_context(patch.object(requirement, '_write_requirement_to_project_json'))
            stack.enter_context(patch.object(requirement, '_generate_task_type', side_effect=task_type))
            later = [stack.enter_context(patch.object(requirement, name)) for name in
                     ('_generate_signals_targets_events', '_generate_metrics',
                      '_generate_targets_from_metrics', '_generate_stop_conditions')]
            completion = stack.enter_context(patch.object(panel, '_on_requirement_ready'))
            requirement.set_completion_callback(completion)
            requirement.on_chat_success('offline requirement')
            self.assertTrue(entered.wait(2))
            panel._sync_task_button()
            self.assertEqual(panel.send_btn.text(), '停止')
            panel.send_btn.click()
            self.pump(lambda: not requirement.chat_worker.isRunning())
            panel._sync_task_button()
            self.assertEqual(panel.send_btn.text(), '发送')
            self.assertTrue(requirement.param_table.isEnabled())
            for operation in later:
                operation.assert_not_called()
            completion.assert_not_called()
        panel._task_button_timer.stop()
        panel.deleteLater()
        requirement.deleteLater()
        self.app.processEvents()

    def test_target_refresh_does_not_rewrite_project_or_duplicate_edit_handlers(self):
        panel = RequirementPanel()
        with patch.object(panel, '_sync_target_value') as sync:
            for _ in range(2):
                panel._update_param_table({'speed': {'target_value': 3, 'unit': 'rad/s'}})
            sync.assert_not_called()
            panel.param_table.item(0, 1).setText('4')
            sync.assert_called_once_with('speed', 4.0)
        panel.deleteLater()
        self.app.processEvents()

    def test_model_http_request_is_actually_aborted(self):
        entered, release = threading.Event(), threading.Event()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                entered.set()
                release.wait(4)
                try:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'{"choices":[{"message":{"content":"late"}}]}')
                except OSError:
                    pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        settings = {'api_key': 'test-only', 'model_name': 'test', 'timeout': 10,
                    'model_url': f'http://127.0.0.1:{server.server_port}/v1'}
        messages = []
        worker = ChatWorker('test', 'test')
        worker.success.connect(messages.append)
        worker.failure.connect(messages.append)
        try:
            with patch('widgets.chat.read_ui_settings', return_value=settings):
                worker.start()
                self.assertTrue(entered.wait(3))
                started = time.monotonic()
                worker.cancel()
                self.assertTrue(worker.wait(1500))
                self.assertLess(time.monotonic() - started, 1.5)
                self.app.processEvents()
                self.assertEqual(messages, [])
        finally:
            worker.cancel()
            worker.wait(1500)
            release.set()
            server.shutdown()
            server.server_close()

    def job_fixture(self, root):
        job = {'task_type': 'test', 'objective': 'speed', 'max_iterations': 3,
               'signals': {'speed': {}}, 'metrics': [{'metric_name': 'steady_state_error'}],
               'paths': {'result_file': 'result.json'}}
        job_file = root / 'job.json'
        job_file.write_text(json.dumps(job), encoding='utf-8')
        saved = {'schema_version': 1, 'job_file': str(job_file), 'job_signature': job_signature(job),
                 'status': 'paused', 'iterations_completed': 1,
                 'rounds': [{'iteration': 1, 'evaluation': {'overall_score': 60}}],
                 'best_state': {'score': 60, 'parameters': {'VEL_KP': 3}}}
        (root / 'result.json').write_text(json.dumps(saved), encoding='utf-8')
        return job_file, job, saved

    @unittest.skipUnless(os.name == 'nt', 'Windows file sharing semantics')
    def test_result_write_recovers_after_real_reader_releases_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'tuning_result.json'
            old = {'status': 'running', 'iterations_completed': 1}
            new = {'status': 'running', 'iterations_completed': 2, 'reason': '调优结果'}
            agent_app.write_result_json(path, old)
            blocked = threading.Event()
            failures = []
            replace = os.replace

            def observed_replace(source, target):
                try:
                    return replace(source, target)
                except PermissionError:
                    blocked.set()
                    raise

            def save():
                try:
                    agent_app.write_result_json(path, new)
                except Exception as exc:
                    failures.append(exc)

            with patch('Optimize.agent_optimize.agent_core.checkpoint.os.replace', side_effect=observed_replace):
                with path.open('r', encoding='utf-8') as reader:
                    writer = threading.Thread(target=save)
                    writer.start()
                    try:
                        self.assertTrue(blocked.wait(1), 'Expected the open reader to block replacement')
                        self.assertEqual(json.load(reader), old)
                    finally:
                        reader.close()
                        writer.join(3)
            self.assertFalse(writer.is_alive())
            self.assertEqual(failures, [])
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), new)
            self.assertEqual(list(Path(temporary).glob('*.tmp')), [])

    def test_result_write_has_unique_temporaries_and_bounded_failures(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'tuning_result.json'
            replace = os.replace
            with patch('Optimize.agent_optimize.agent_core.checkpoint.os.replace', wraps=replace) as writes:
                for iteration in (1, 2):
                    agent_app.write_result_json(path, {'iterations_completed': iteration})
            names = [call.args[0] for call in writes.call_args_list]
            self.assertEqual(len(set(names)), 2)
            self.assertTrue(all(name.parent == path.parent for name in names))
            old = path.read_bytes()
            with patch('Optimize.agent_optimize.agent_core.checkpoint.os.replace', side_effect=PermissionError('locked')) as writes, \
                    patch('Optimize.agent_optimize.agent_core.checkpoint.time.sleep') as sleeps:
                with self.assertRaises(PermissionError):
                    agent_app.write_result_json(path, {'iterations_completed': 3})
            self.assertEqual(writes.call_count, 21)
            self.assertEqual(sleeps.call_count, 20)
            self.assertEqual(path.read_bytes(), old)
            self.assertEqual(list(Path(temporary).glob('*.tmp')), [])
            with patch('Optimize.agent_optimize.agent_core.checkpoint.os.replace', side_effect=OSError('disk error')) as writes, \
                    patch('Optimize.agent_optimize.agent_core.checkpoint.time.sleep') as sleeps:
                with self.assertRaises(OSError):
                    agent_app.write_result_json(path, {'iterations_completed': 3})
            writes.assert_called_once()
            sleeps.assert_not_called()
            self.assertEqual(path.read_bytes(), old)
            self.assertEqual(list(Path(temporary).glob('*.tmp')), [])

    def test_stop_saves_paused_checkpoint_using_shared_writer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / 'project.json'
            project.write_text('{}', encoding='utf-8')
            result_file = root / 'candidates/candidate_01/log/optimize/tuning_result.json'
            saved = {'status': 'running', 'iterations_completed': 1, 'rounds': [{'iteration': 1}]}
            agent_app.write_result_json(result_file, saved)
            notices = []
            panel = SimpleNamespace(set_tuning_active=lambda active: None, _append_notice=notices.append)
            window = SimpleNamespace(right_panel=lambda: SimpleNamespace(main_program_panel=panel),
                                     get_current_project_json_path=lambda: str(project))
            with patch('ui_main.write_result_json', wraps=agent_app.write_result_json) as write:
                MainWindow._on_task_tree_stopped(window)
            saved['status'] = 'paused'
            write.assert_called_once_with(result_file, saved)
            self.assertEqual(json.loads(result_file.read_text(encoding='utf-8')), saved)
            self.assertTrue(notices)

    def test_headless_resume_keeps_completed_iterations_and_best_parameters(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job_file, job, saved = self.job_fixture(root)
            ctx = ProjectContext(root, root / 'agent.json', root, {'automation': {}})
            with patch.object(agent_app, 'run_agent_turn', return_value={'content': 'done'}) as turns, \
                    patch.object(agent_app, '_load_latest_evaluation_result', return_value={'status': 'ok', 'overall_score': 75}), \
                    redirect_stdout(io.StringIO()):
                code = agent_app.run_headless_job(job_file, None, None, ctx, resume=True)
            result = json.loads((root / 'result.json').read_text(encoding='utf-8'))
            self.assertEqual(code, 0)
            self.assertEqual(turns.call_count, 2)
            self.assertEqual([x['iteration'] for x in result['rounds']], [1, 2, 3])
            self.assertEqual(result['rounds'][0]['evaluation']['overall_score'], 60)
            self.assertEqual(ctx.automation()['_optimization_best_state'], saved['best_state'])

    def test_changed_requirements_do_not_reuse_old_scores(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job_file, job, _ = self.job_fixture(root)
            job['objective'] = 'new target speed'
            job_file.write_text(json.dumps(job), encoding='utf-8')
            self.assertEqual(load_checkpoint(root / 'result.json', job_file, job), {})
            ctx = ProjectContext(root, root / 'agent.json', root, {'automation': {}})
            with patch.object(agent_app, 'run_agent_turn', return_value={'content': 'done'}) as turns, \
                    patch.object(agent_app, '_load_latest_evaluation_result', return_value={'status': 'ok', 'overall_score': 75}), \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(agent_app.run_headless_job(job_file, None, None, ctx, resume=True), 0)
            self.assertEqual(turns.call_count, 3)

    def test_resume_skips_completed_candidates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job_file, job, saved = self.job_fixture(root)
            candidate = root / 'candidate_01'
            candidate.mkdir()
            target = candidate / 'candidate.json'
            target.write_text(json.dumps(job), encoding='utf-8')
            saved.update(job_file=str(target), status='completed')
            saved['iterations_completed'] = 3
            saved['rounds'] = [{'iteration': i} for i in range(1, 4)]
            result_file = root / 'result.json'
            result_file.write_text(json.dumps(saved), encoding='utf-8')
            with patch.object(competition_runner, 'build_optimize_command', return_value=([], {}, {'tuning_result': str(result_file)})), \
                    patch.object(competition_runner, 'write_candidate_evidence', return_value=root / 'evidence.json') as evidence, \
                    patch.object(competition_runner.subprocess, 'Popen') as launch, redirect_stdout(io.StringIO()):
                result = competition_runner.run_optimize_for_candidate(candidate, dry_run=False, resume=True)
            launch.assert_not_called()
            self.assertTrue(result['resumed_completed'])
            evidence.assert_called_once_with(candidate)
            self.assertEqual(result['outputs']['candidate_evidence'], str(root / 'evidence.json'))

    def test_resume_does_not_skip_a_result_from_another_optimization_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, job, saved = self.job_fixture(root)
            candidate = root / 'candidate_01'
            candidate.mkdir()
            job_file = candidate / 'candidate.json'
            job['_optimization_run_id'] = 'previous-run'
            saved.update(job_file=str(job_file), status='completed', job_signature=job_signature(job),
                         iterations_completed=3, rounds=[{'iteration': i} for i in range(1, 4)])
            result_file = root / 'result.json'
            result_file.write_text(json.dumps(saved), encoding='utf-8')
            job['_optimization_run_id'] = 'current-run'
            job_file.write_text(json.dumps(job), encoding='utf-8')
            with patch.object(competition_runner, 'build_optimize_command', return_value=(['test'], {}, {'tuning_result': str(result_file)})), \
                    patch.object(competition_runner, 'write_candidate_evidence', return_value=root / 'evidence.json'), \
                    patch.object(competition_runner.subprocess, 'Popen') as launch, redirect_stdout(io.StringIO()):
                launch.return_value.__enter__.return_value.stdout = io.StringIO('')
                launch.return_value.__enter__.return_value.wait.return_value = 0
                result = competition_runner.run_optimize_for_candidate(candidate, dry_run=False, resume=True)
            launch.assert_called_once()
            self.assertNotIn('resumed_completed', result)

    def test_pausing_between_rounds_cancels_pending_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / 'project.json'
            project.write_text('{}', encoding='utf-8')
            stopped = []
            window = SimpleNamespace(_round_transition_token=3,
                _scheduled_next_round=(str(project), 2), _competition_process=None,
                get_current_project_json_path=lambda: str(project),
                _on_task_tree_stopped=lambda: stopped.append(True))
            MainWindow.stop_agent_optimization(window)
            self.assertEqual(window._round_transition_token, 4)
            self.assertIsNone(window._scheduled_next_round)
            self.assertEqual(stopped, [True])
            marker = project.parent / 'log/ui/paused_task.json'
            self.assertEqual(json.loads(marker.read_text())['round'], 2)
            MainWindow.stop_agent_optimization(window)
            self.assertEqual(json.loads(marker.read_text())['round'], 2, 'A stop retry must keep the paused round')

    def test_history_cannot_switch_project_while_task_is_running(self):
        messages = []
        panel = SimpleNamespace(_assistant_busy=lambda: True, _stopping=False,
                                _append_notice=messages.append)
        window = SimpleNamespace(current_project_json_path='original',
            right_panel=lambda: SimpleNamespace(main_program_panel=panel))
        MainWindow._on_history_project_opened(window, Path('unopened.json'))
        self.assertEqual(window.current_project_json_path, 'original')
        self.assertEqual(len(messages), 1)

    def test_resume_optimization_does_not_regenerate_completed_sources(self):
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            root = Path(temporary)
            project = root / 'project.json'
            project.write_text('{"max_rounds": 2}', encoding='utf-8')
            round_dir = root / 'rounds/round_02'
            round_dir.mkdir(parents=True)
            (round_dir / 'run_state.json').write_text('{"phase":"optimization"}', encoding='utf-8')
            (round_dir / 'candidate_profiles.json').write_text('{}', encoding='utf-8')
            candidate = root / 'candidates/candidate_01'
            candidate.mkdir(parents=True)
            stack.enter_context(redirect_stdout(io.StringIO()))
            stack.enter_context(patch.object(competition_runner, 'write_common_requirement_snapshot'))
            stack.enter_context(patch.object(competition_runner, 'ensure_candidates', return_value=[candidate]))
            stack.enter_context(patch.object(competition_runner, 'configure_optimize', return_value=[]))
            generate = stack.enter_context(patch.object(competition_runner, 'generate_candidates'))
            optimize = stack.enter_context(patch.object(competition_runner, 'run_optimize', return_value=[]))
            stack.enter_context(patch.object(competition_runner, 'read_score', return_value={}))
            stack.enter_context(patch('Competition.round_feedback.generate_round_feedback', return_value=round_dir / 'feedback.json'))
            competition_runner.run_competition(project, candidates=1, parallel=1, optimize_parallel=1,
                dry_run=False, skip_generate=False, skip_optimize=False, force_init=False,
                single_round=True, round_number=2, resume=True)
            generate.assert_not_called()
            optimize.assert_called_once_with([candidate], parallel=1, dry_run=False, resume=True)

    def test_interrupted_header_write_preserves_previous_header(self):
        with tempfile.TemporaryDirectory() as temporary:
            header = Path(temporary) / 'paras.h'
            header.write_text('#define VEL_KP 3.0f\n', encoding='utf-8')
            with patch.object(Path, 'replace', side_effect=OSError('simulated interruption')):
                with self.assertRaises(ParameterHeaderFileError):
                    _write_text(header, '#define VEL_KP 6.0f\n')
            self.assertEqual(header.read_text(encoding='utf-8'), '#define VEL_KP 3.0f\n')

    def test_remote_marker_survives_transport_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = root / 'simulation/remote_active.json'
            with patch.object(remote_sil_client, '_post_json', side_effect=RuntimeError('connection lost')):
                with self.assertRaises(RuntimeError):
                    remote_sil_client._post_job(root / 'agent.json', 'http://127.0.0.1:1', 'run_simulation', {'job_id': 'job'}, 1)
            saved = json.loads(marker.read_text(encoding='utf-8'))
            self.assertEqual(saved['job_id'], 'job')
            self.assertEqual(len(saved['cancel_token']), 32)

    def test_remote_cancel_requires_matching_token_and_releases_worker(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = SilWorkerState({'job_root': temporary})
            entered = threading.Event()

            def running(request, started_at):
                entered.set()
                state.active_job['cancelled'].wait(3)
                return 499, {'ok': False, 'error': 'cancelled'}

            with patch.object(state, '_run_simulation_locked', side_effect=running), \
                    patch.object(state, '_stop_process') as stop:
                thread = threading.Thread(target=lambda: state.run_simulation({'job_id': 'mine', 'cancel_token': 'secret'}))
                thread.start()
                try:
                    self.assertTrue(entered.wait(2))
                    self.assertEqual(state.cancel_simulation({'job_id': 'mine', 'cancel_token': 'wrong'})[0], 409)
                    self.assertFalse(state.active_job['cancelled'].is_set())
                    stop.assert_not_called()
                    status, result = state.cancel_simulation({'job_id': 'mine', 'cancel_token': 'secret'})
                    self.assertEqual(status, 200)
                    self.assertEqual(result['status'], 'cancelled')
                    thread.join(2)
                    self.assertFalse(thread.is_alive())
                    self.assertIsNone(state.active_job)
                    self.assertFalse(state.lock.locked())
                finally:
                    if state.active_job:
                        state.active_job['cancelled'].set()
                    thread.join(4)

    def test_remote_cancellation_arriving_before_start_prevents_late_job(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = SilWorkerState({'job_root': temporary})
            request = {'job_id': 'mine', 'cancel_token': 'secret'}
            self.assertEqual(state.cancel_simulation(request)[0], 200)
            with patch.object(state, '_run_simulation_locked') as run:
                self.assertEqual(state.run_simulation(request)[0], 409)
                run.assert_not_called()
            self.assertFalse(state.lock.locked())

    def test_stop_checks_for_remote_markers_created_during_local_shutdown(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = root / 'candidates/candidate_01/log/optimize/simulation/remote_active.json'

            def local_shutdown(*args, **kwargs):
                marker.parent.mkdir(parents=True)
                marker.write_text(json.dumps({'worker_url': 'http://127.0.0.1:1',
                    'job_id': 'late', 'cancel_token': 'secret'}), encoding='utf-8')
                return SimpleNamespace(returncode=0)

            worker = StopProcessWorker(123, remote_marker_root=root)
            with patch('workflow.task_control.subprocess.run', side_effect=local_shutdown), \
                    patch('workflow.task_control.urllib.request.urlopen', return_value=io.BytesIO(b'{"ok":true}')) as post:
                worker.run()
            self.assertEqual(worker.error, '')
            self.assertFalse(marker.exists())
            request = post.call_args.args[0]
            self.assertEqual(json.loads(request.data), {'job_id': 'late', 'cancel_token': 'secret'})

    @unittest.skipUnless(os.name == 'nt', 'Windows batch launching')
    def test_legacy_launcher_waits_for_owned_child_and_forwards_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'path with spaces 中文'
            root.mkdir()
            project = root / 'project test.json'
            project.write_text('{}', encoding='utf-8')
            output = root / 'args.json'
            script = root / 'fake agent.py'
            script.write_text('import json,sys,time\nfrom pathlib import Path\n'
                'time.sleep(0.1)\n'
                f'Path({str(output)!r}).write_text(json.dumps(sys.argv[1:]), encoding="utf-8")\n', encoding='utf-8')
            bat = root / 'run_tuning_agent.bat'
            bat.write_text(f'@echo off\nchcp 65001 >nul\n"%MOTORAI_AGENT_PYTHON%" "{script}" %*\nexit /b %ERRORLEVEL%\n', encoding='utf-8')
            config = {'config_project': str(script), 'run_tuning_agent': str(bat)}
            messages = io.StringIO()
            with patch.object(legacy_launcher, 'load_settings', return_value={}), \
                    patch.object(legacy_launcher, 'normalize_optimize_config', return_value=config), \
                    patch.object(legacy_launcher, 'optimize_project_is_current', return_value=True), \
                    patch.object(legacy_launcher, '_sync_target_velocity_for_ui_project'), redirect_stdout(messages):
                code = legacy_launcher.run_agent_optimization(str(project), resume=True)
            self.assertEqual(code, 0, messages.getvalue())
            self.assertEqual(json.loads(output.read_text()), [str(project), '--resume'])

    @unittest.skipUnless(os.name == 'nt', 'Windows process-tree semantics')
    def test_stop_kills_own_descendants_and_leaves_other_process_alive(self):
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pid_file = root / 'child.pid'
            script = root / 'parent.py'
            script.write_text('import subprocess,sys,time\nfrom pathlib import Path\n'
                              'child=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"],creationflags=0x08000000)\n'
                              'Path(sys.argv[1]).write_text(str(child.pid))\ntime.sleep(30)\n', encoding='utf-8')
            parent = subprocess.Popen([sys.executable, str(script), str(pid_file)], creationflags=0x08000000)
            other = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(30)'], creationflags=0x08000000)
            child_handle = None
            try:
                deadline = time.monotonic() + 5
                while not pid_file.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(pid_file.exists())
                child_handle = kernel.OpenProcess(0x1001, False, int(pid_file.read_text()))
                self.assertTrue(child_handle)
                stopper = StopProcessWorker(parent.pid)
                stopper.start()
                self.assertTrue(stopper.wait(7000))
                self.assertEqual(stopper.error, '')
                parent.wait(timeout=3)
                code = wintypes.DWORD()
                self.assertTrue(kernel.GetExitCodeProcess(child_handle, ctypes.byref(code)))
                self.assertNotEqual(code.value, 259)
                self.assertIsNone(other.poll())
            finally:
                for process in (parent, other):
                    if process.poll() is None:
                        stopper = StopProcessWorker(process.pid)
                        stopper.start()
                        stopper.wait(7000)
                        process.wait(timeout=3)
                if child_handle:
                    kernel.TerminateProcess(child_handle, 1)
                    kernel.CloseHandle(child_handle)


if __name__ == '__main__':
    unittest.main()
