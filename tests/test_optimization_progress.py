"""Offline checks for live logs, UI progress and round boundaries."""
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from Competition import competition_runner as runner


class OptimizationProgressTests(unittest.TestCase):
    def test_candidate_logs_are_readable_before_process_exits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / 'candidate_01'
            candidate.mkdir()
            release = root / 'release'
            script = root / 'agent.py'
            script.write_text(
                'import os, sys, time\n'
                'from pathlib import Path\n'
                'print("[stage] 仿真运行中", flush=True)\n'
                'print("运行诊断", file=sys.stderr, flush=True)\n'
                'assert os.environ["PYTHONUNBUFFERED"] == "1"\n'
                'deadline = time.monotonic() + 10\n'
                'while not Path(sys.argv[1]).exists() and time.monotonic() < deadline:\n'
                '    time.sleep(0.02)\n'
                'sys.exit(7)\n', encoding='utf-8')
            stdout = candidate / 'log/optimize/run_optimize_stdout.txt'
            stderr = candidate / 'log/optimize/run_optimize_stderr.txt'
            results = []
            errors = []
            parent_stderr = io.StringIO()

            def run():
                try:
                    results.append(runner.run_optimize_for_candidate(candidate, dry_run=False))
                except Exception as exc:
                    errors.append(exc)

            with patch.object(runner, 'build_optimize_command', return_value=(
                    [sys.executable, str(script), str(release)],
                    {'PYTHONUNBUFFERED': '1', 'PYTHONIOENCODING': 'utf-8'}, {})), \
                    patch.object(runner, '_sync_target_velocity_for_candidate'), \
                    redirect_stdout(io.StringIO()), redirect_stderr(parent_stderr):
                thread = threading.Thread(target=run)
                thread.start()
                try:
                    deadline = time.monotonic() + 6
                    while time.monotonic() < deadline:
                        if (stdout.exists() and '仿真运行中' in stdout.read_text(encoding='utf-8')
                                and stderr.exists() and '运行诊断' in stderr.read_text(encoding='utf-8')):
                            break
                        time.sleep(0.02)
                    self.assertTrue(thread.is_alive(), 'Logs must exist while the agent is still running')
                    self.assertIn('仿真运行中', stdout.read_text(encoding='utf-8'))
                    self.assertIn('运行诊断', stderr.read_text(encoding='utf-8'))
                finally:
                    release.touch()
                    thread.join(timeout=12)
                self.assertFalse(thread.is_alive())
                self.assertEqual(errors, [])
                self.assertEqual(results[0]['returncode'], 7)
                self.assertEqual(results[0]['status'], 'failed')
                self.assertIn('candidate_01 调优失败（返回码 7）', parent_stderr.getvalue())
                self.assertIn('运行诊断', parent_stderr.getvalue())

    def run_round(self, *, single_round=False, score=70, max_rounds=2,
                  round_number=1, failure=False, feedback_failure=False):
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            root = Path(temporary)
            project = root / 'project.json'
            project.write_text(json.dumps({'max_rounds': max_rounds, 'stop_conditions': {
                'overall_score_min': 85, 'metric_score_min': 80, 'metric_error_count_max': 0
            }}), encoding='utf-8')
            candidate = root / 'candidates/candidate_01'
            candidate.mkdir(parents=True)
            scoreboard_item = {
                'candidate_id': candidate.name, 'status': 'completed', 'overall_score': score,
                'metric_error_count': 0, 'metric_ok_count': 2,
                'final_evaluation': {'min_metric_score': score, 'status': 'ok'},
            }

            def feedback(project_json, round_number=1):
                if feedback_failure:
                    raise RuntimeError('feedback failed')
                p = root / 'rounds' / f'round_{round_number:02d}' / 'round_feedback.json'
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('{}', encoding='utf-8')
                return p

            stack.enter_context(redirect_stdout(io.StringIO()))
            stack.enter_context(patch.object(runner, 'write_common_requirement_snapshot'))
            stack.enter_context(patch.object(runner, 'ensure_candidates', return_value=[candidate]))
            stack.enter_context(patch.object(runner, 'configure_optimize', return_value=[]))
            stack.enter_context(patch.object(runner, 'generate_candidates', return_value={
                'results': [{'candidate_id': candidate.name, 'status': 'completed'}]
            }))
            optimize = stack.enter_context(patch.object(runner, 'run_optimize', return_value=[{
                'candidate_id': candidate.name, 'status': 'failed' if failure else 'completed'
            }]))
            stack.enter_context(patch.object(runner, 'read_score', return_value=scoreboard_item))
            fb = stack.enter_context(patch('Competition.round_feedback.generate_round_feedback', side_effect=feedback))
            def make_strategy(project_json, from_round=1, to_round=2, **kwargs):
                p = root / 'rounds' / f'round_{to_round:02d}' / 'candidate_profiles.json'
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('{}', encoding='utf-8')
                return {'candidate_profiles': 'next.json'}
            strategy = stack.enter_context(patch('Competition.next_round_strategy.generate_next_round_strategy',
                                                side_effect=make_strategy))
            result = runner.run_competition(
                project, candidates=1, parallel=1, optimize_parallel=1, dry_run=False,
                skip_generate=True, skip_optimize=False, force_init=False,
                round_number=round_number, single_round=single_round)
            return result, optimize.call_count, strategy.call_count, fb.call_count

    def test_ui_single_round_returns_without_running_the_next_round(self):
        result, runs, strategies, feedbacks = self.run_round(single_round=True)
        self.assertEqual((runs, strategies, feedbacks), (1, 1, 1))
        self.assertEqual(result['round_number'], 1)
        self.assertEqual(result['next_round_profiles'], 'next.json')

    def test_cli_stops_when_requirements_are_satisfied_even_without_round_limit(self):
        result, runs, strategies, _ = self.run_round(score=90, max_rounds=0)
        self.assertEqual((runs, strategies), (1, 0))
        self.assertTrue(result['requirement_satisfied'])

    def test_cli_respects_round_limit_and_continues_unsatisfied_rounds(self):
        result, runs, strategies, _ = self.run_round()
        self.assertEqual((runs, strategies), (2, 1))
        self.assertEqual(result['round_number'], 2)

    def test_failed_candidate_does_not_launch_another_round(self):
        result, runs, strategies, feedbacks = self.run_round(failure=True)
        self.assertEqual((runs, strategies, feedbacks), (1, 0, 0))
        self.assertEqual(result['optimize'][0]['status'], 'failed')

    def test_feedback_failure_is_reported(self):
        with self.assertRaisesRegex(RuntimeError, '反馈或下一轮策略生成失败'):
            self.run_round(single_round=True, feedback_failure=True)

    def test_ui_handles_split_utf8_and_preserves_full_stdout(self):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PyQt5.QtCore import QProcess
        from PyQt5.QtWidgets import QApplication
        sys.path.insert(0, str(ROOT / 'Generate/ui'))
        from ui_main import MainWindow
        app = QApplication.instance() or QApplication([])
        messages, statuses = [], []
        panel = SimpleNamespace(_append_debug=messages.append, _set_status_text=statuses.append)
        window = SimpleNamespace(right_panel=lambda: SimpleNamespace(main_program_panel=panel))
        process = QProcess()
        process._motorai_progress_buffer = b''
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / 'stdout.txt'
            process.readyReadStandardOutput.connect(
                lambda: MainWindow._read_competition_progress(window, process, log))
            # Split a multibyte character across two OS writes.
            process.start(sys.executable, ['-u', '-c',
                'import sys,time\n'
                'data="[progress] candidate_01：仿真完成。\\n{\\\"result\\\":1}\\n".encode("utf-8")\n'
                'sys.stdout.buffer.write(data[:28]);sys.stdout.buffer.flush()\n'
                'time.sleep(0.08)\n'
                'sys.stdout.buffer.write(data[28:]);sys.stdout.buffer.flush()'])
            self.assertTrue(process.waitForFinished(6000))
            app.processEvents()
            MainWindow._read_competition_progress(window, process, log)
            self.assertEqual(process.exitCode(), 0)
            self.assertEqual(messages, ['candidate_01：仿真完成。'])
            self.assertEqual(statuses, ['状态：candidate_01：仿真完成。'])
            self.assertIn('{"result":1}', log.read_text(encoding='utf-8'))

    def test_ui_launches_single_round_without_forcing_more_rounds(self):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PyQt5.QtWidgets import QApplication
        sys.path.insert(0, str(ROOT / 'Generate/ui'))
        from ui_main import MainWindow
        app = QApplication.instance() or QApplication([])
        panel = SimpleNamespace(_append_debug=lambda text: None, _set_status_text=lambda text: None,
                                set_tuning_active=lambda active: None)
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / 'project.json'
            project.write_text(json.dumps({'workspace_mode': 'competition',
                                           'candidate_count': 2, 'max_iterations': 4}), encoding='utf-8')
            window = SimpleNamespace(get_current_project_json_path=lambda: str(project),
                                     right_panel=lambda: SimpleNamespace(main_program_panel=panel))
            with patch('ui_main.QProcess') as process_class:
                MainWindow.run_agent_optimization(window, round_number=2)
                executable, args = process_class.return_value.start.call_args.args
                self.assertEqual(executable, sys.executable)
                self.assertIn('--single-round', args)
                self.assertNotIn('--force-next-round', args)
                self.assertEqual(args[args.index('--round') + 1], '2')
                self.assertEqual(args[0], '-u')


if __name__ == '__main__':
    unittest.main()
