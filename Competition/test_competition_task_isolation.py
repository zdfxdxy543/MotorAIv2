import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MOTORAI_ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = MOTORAI_ROOT / "Generate" / "ui"
for import_root in (MOTORAI_ROOT, UI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from Competition import competition_runner
from Optimize.agent_optimize.agent_core.app import stop_condition_met
from ui_main import MainWindow


class CompetitionRoundOwnershipTests(unittest.TestCase):
    def _run_competition(
        self,
        *,
        satisfied: bool,
        force_next_round: bool,
        max_rounds=2,
    ):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        project_a = root / "project_a" / "project_a.json"
        project_b = root / "project_b" / "project_b.json"
        project_a.parent.mkdir(parents=True)
        project_b.parent.mkdir(parents=True)
        project_a.write_text(
            json.dumps({"candidate_count": 1, "max_rounds": max_rounds}),
            encoding="utf-8",
        )
        project_b.write_text(
            json.dumps({"candidate_count": 1, "max_rounds": 2}),
            encoding="utf-8",
        )

        candidate = project_a.parent / "candidates" / "candidate_01"
        candidate.mkdir(parents=True)
        optimize_projects = []
        generate_projects = []
        strategy_projects = []
        feedback_rounds = []

        def fake_optimize(candidate_dirs, *, parallel, dry_run):
            optimize_projects.append([path.parent.parent.resolve() for path in candidate_dirs])
            return []

        def fake_generate(project_json, selectors, *, parallel, dry_run):
            generate_projects.append(Path(project_json).resolve())
            return {"results": [{"status": "completed"}]}

        def fake_feedback(project_json, *, round_number):
            project_json = Path(project_json).resolve()
            feedback_rounds.append((project_json, round_number))
            output = project_json.parent / "rounds" / f"round_{round_number:02d}" / "round_feedback.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(
                    {
                        "round": round_number,
                        "requirement_satisfied": satisfied,
                        "winner": {
                            "candidate_id": "candidate_01",
                            "overall_score": 90,
                        },
                        "scoreboard": [
                            {"candidate_id": "candidate_01", "overall_score": 90}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            return output

        def fake_strategy(project_json, *, from_round, to_round, candidate_count):
            project_json = Path(project_json).resolve()
            strategy_projects.append(project_json)
            output = project_json.parent / "rounds" / f"round_{to_round:02d}" / "candidate_profiles.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("{}", encoding="utf-8")
            return {"candidate_profiles": str(output)}

        score = {
            "candidate_id": "candidate_01",
            "status": "completed",
            "overall_score": 90,
            "final_evaluation": {},
        }
        with (
            patch.object(competition_runner, "write_common_requirement_snapshot"),
            patch.object(competition_runner, "ensure_candidates", return_value=[candidate]),
            patch.object(competition_runner, "configure_optimize", return_value=[]),
            patch.object(competition_runner, "run_optimize", side_effect=fake_optimize),
            patch.object(competition_runner, "generate_candidates", side_effect=fake_generate),
            patch.object(competition_runner, "read_score", return_value=score),
            patch("Competition.round_feedback.generate_round_feedback", side_effect=fake_feedback),
            patch("Competition.next_round_strategy.generate_next_round_strategy", side_effect=fake_strategy),
        ):
            competition_runner.run_competition(
                project_a,
                candidates=1,
                parallel=1,
                optimize_parallel=1,
                dry_run=False,
                skip_generate=True,
                skip_optimize=False,
                force_init=False,
                force_next_round=force_next_round,
                round_number=1,
            )

        return {
            "project_a": project_a.resolve(),
            "project_b": project_b.resolve(),
            "optimize_projects": optimize_projects,
            "generate_projects": generate_projects,
            "strategy_projects": strategy_projects,
            "feedback_rounds": feedback_rounds,
        }

    def test_unsatisfied_rounds_keep_the_original_project(self):
        calls = self._run_competition(satisfied=False, force_next_round=False)
        project_a_root = calls["project_a"].parent

        self.assertEqual(len(calls["optimize_projects"]), 2)
        self.assertTrue(
            all(
                project_roots == [project_a_root]
                for project_roots in calls["optimize_projects"]
            )
        )
        self.assertEqual(calls["generate_projects"], [calls["project_a"]])
        self.assertEqual(calls["strategy_projects"], [calls["project_a"]])
        self.assertEqual(
            calls["feedback_rounds"],
            [(calls["project_a"], 1), (calls["project_a"], 2)],
        )
        self.assertNotIn(calls["project_b"], calls["generate_projects"])

    def test_satisfied_big_round_still_runs_to_configured_limit(self):
        calls = self._run_competition(satisfied=True, force_next_round=False)

        self.assertEqual(len(calls["optimize_projects"]), 2)
        self.assertEqual(calls["generate_projects"], [calls["project_a"]])
        self.assertEqual(calls["strategy_projects"], [calls["project_a"]])
        self.assertEqual(
            calls["feedback_rounds"],
            [(calls["project_a"], 1), (calls["project_a"], 2)],
        )

    def test_legacy_force_flag_does_not_change_big_round_limit(self):
        calls = self._run_competition(satisfied=True, force_next_round=True)

        self.assertEqual(len(calls["optimize_projects"]), 2)
        self.assertEqual(calls["strategy_projects"], [calls["project_a"]])
        self.assertEqual(
            calls["feedback_rounds"],
            [(calls["project_a"], 1), (calls["project_a"], 2)],
        )

    def test_invalid_big_round_limit_runs_once(self):
        calls = self._run_competition(
            satisfied=False,
            force_next_round=False,
            max_rounds=0,
        )

        self.assertEqual(len(calls["optimize_projects"]), 1)
        self.assertEqual(calls["generate_projects"], [])
        self.assertEqual(calls["strategy_projects"], [])
        self.assertEqual(calls["feedback_rounds"], [(calls["project_a"], 1)])


class SmallIterationStopTests(unittest.TestCase):
    def test_small_iteration_can_still_stop_when_all_conditions_are_met(self):
        evaluation = {
            "overall_score": 90,
            "metric_error_count": 0,
            "min_metric_score": 85,
        }
        conditions = {
            "overall_score_min": 85,
            "metric_error_count_max": 0,
            "metric_score_min": 80,
        }

        self.assertTrue(stop_condition_met(evaluation, conditions))


class CompletionIsolationTests(unittest.TestCase):
    def test_background_project_completion_does_not_touch_current_project_ui(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_a = root / "project_a" / "project_a.json"
            project_b = root / "project_b" / "project_b.json"
            project_a.parent.mkdir(parents=True)
            project_b.parent.mkdir(parents=True)
            project_a.write_text("{}", encoding="utf-8")
            project_b.write_text("{}", encoding="utf-8")

            feedback_path = project_a.parent / "rounds" / "round_01" / "round_feedback.json"
            feedback_path.parent.mkdir(parents=True)
            feedback_path.write_text(
                json.dumps(
                    {
                        "requirement_satisfied": False,
                        "winner": {
                            "candidate_id": "candidate_01",
                            "overall_score": 80,
                        },
                        "scoreboard": [],
                    }
                ),
                encoding="utf-8",
            )

            class FakeProcess:
                def __init__(self):
                    self.deleted = False

                def deleteLater(self):
                    self.deleted = True

            class FakeWindow:
                def __init__(self, process):
                    self._competition_process = process
                    self._competition_project_json_path = project_a

                def get_current_project_json_path(self):
                    return project_b

                def right_panel(self):
                    raise AssertionError("background completion touched the current project UI")

            process = FakeProcess()
            window = FakeWindow(process)
            MainWindow._on_competition_finished(
                window,
                0,
                0,
                project_a,
                process,
            )

            self.assertTrue(process.deleted)
            self.assertIsNone(window._competition_process)
            self.assertIsNone(window._competition_project_json_path)


if __name__ == "__main__":
    unittest.main()
