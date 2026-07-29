import json
import sys
import tempfile
import unittest
from pathlib import Path

MOTORAI_ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = MOTORAI_ROOT / "Generate" / "ui"
if str(UI_ROOT) not in sys.path:
    sys.path.insert(0, str(UI_ROOT))

from Competition.competition_workspace import (
    build_candidate_generation_requirement,
    candidate_design_profile,
    detect_controller_method,
    write_candidate_profiles,
)
from Competition.next_round_strategy import _apply_controller_method_allocation
from panels.main_program import MainProgramPanel


class FirstRoundControllerAllocationTests(unittest.TestCase):
    def test_detects_only_an_explicit_single_method(self):
        self.assertEqual(detect_controller_method("速度环采用 PID 控制器"), "pid")
        self.assertEqual(detect_controller_method("请设计基于 LADRC 的转速控制"), "ladrc")
        self.assertEqual(detect_controller_method("位置环使用滑模控制"), "smc")
        self.assertIsNone(detect_controller_method("请设计电机转速控制器"))
        self.assertIsNone(detect_controller_method("请比较 PID 控制和 LADRC 控制"))
        self.assertIsNone(detect_controller_method("不要使用 PID 控制"))
        self.assertIsNone(detect_controller_method("后续可考虑 PID 控制"))
        self.assertEqual(detect_controller_method("不采用 PID，改用 LADRC 控制"), "ladrc")

    def test_unspecified_method_is_paired_between_pid_and_ladrc(self):
        profiles = [candidate_design_profile(index) for index in range(1, 5)]

        self.assertEqual(
            [profile["preferred_control_methods"] for profile in profiles],
            [["pid"], ["ladrc"], ["pid"], ["ladrc"]],
        )
        self.assertEqual(profiles[0]["name"], profiles[1]["name"])
        self.assertEqual(profiles[2]["name"], profiles[3]["name"])
        self.assertTrue(
            all(
                profile["controller_assignment"]["source"] == "balanced_first_round"
                for profile in profiles
            )
        )

    def test_explicit_method_is_applied_to_every_candidate(self):
        profiles = [
            candidate_design_profile(index, controller_method="ladrc")
            for index in range(1, 5)
        ]

        self.assertTrue(
            all(profile["preferred_control_methods"] == ["ladrc"] for profile in profiles)
        )
        self.assertEqual(len({profile["name"] for profile in profiles}), 4)

    def test_assigned_method_is_a_hard_generation_constraint(self):
        profile = candidate_design_profile(2)
        requirement = build_candidate_generation_requirement("控制电机转速", profile)

        self.assertIn("必须使用的控制方法", requirement)
        self.assertIn("ladrc", requirement)

    def test_reassignment_preserves_non_method_candidate_customization(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            profiles = write_candidate_profiles(project_root, 2)
            profiles[0]["llm_temperature"] = 0.77
            (project_root / "common" / "candidate_profiles.json").write_text(
                json.dumps({"profiles": profiles}, ensure_ascii=False),
                encoding="utf-8",
            )

            reassigned = write_candidate_profiles(
                project_root,
                2,
                controller_method="ladrc",
                preserve_existing=True,
            )

            self.assertEqual(reassigned[0]["llm_temperature"], 0.77)
            self.assertEqual(reassigned[0]["preferred_control_methods"], ["ladrc"])
            self.assertEqual(reassigned[1]["preferred_control_methods"], ["ladrc"])


class LaterRoundControllerAllocationTests(unittest.TestCase):
    @staticmethod
    def _feedback():
        return {
            "winner": {"candidate_id": "candidate_02", "overall_score": 92.0},
            "candidates": [
                {
                    "candidate_id": "candidate_01",
                    "overall_score": 80.0,
                    "structure_manifest": {"control_methods": ["pid"]},
                },
                {
                    "candidate_id": "candidate_02",
                    "overall_score": 92.0,
                    "structure_manifest": {"control_methods": ["ladrc"]},
                },
                {
                    "candidate_id": "candidate_03",
                    "overall_score": 85.0,
                    "structure_manifest": {"control_methods": ["pid"]},
                },
                {
                    "candidate_id": "candidate_04",
                    "overall_score": 88.0,
                    "structure_manifest": {"control_methods": ["ladrc"]},
                },
            ],
        }

    @staticmethod
    def _profiles():
        return [
            {
                "candidate_id": "candidate_01",
                "reference_candidates": ["candidate_01"],
                "parameter_seed_policy": {
                    "mode": "inherit",
                    "source_candidate": "candidate_01",
                    "perturbation_direction": "",
                },
            },
            {
                "candidate_id": "candidate_02",
                "reference_candidates": [],
                "parameter_seed_policy": {
                    "mode": "fresh",
                    "source_candidate": "",
                    "perturbation_direction": "",
                },
            },
            {
                "candidate_id": "candidate_03",
                "reference_candidates": ["candidate_01"],
                "parameter_seed_policy": {
                    "mode": "inherit_then_perturb",
                    "source_candidate": "candidate_01",
                    "perturbation_direction": "原策略",
                },
            },
            {
                "candidate_id": "candidate_04",
                "reference_candidates": ["candidate_02"],
                "parameter_seed_policy": {
                    "mode": "inherit",
                    "source_candidate": "candidate_02",
                    "perturbation_direction": "",
                },
            },
        ]

    def test_winner_method_gets_majority_and_challenger_keeps_one_slot(self):
        profiles, allocation = _apply_controller_method_allocation(
            self._profiles(),
            self._feedback(),
            "请设计电机转速控制器",
        )

        methods = [profile["preferred_control_methods"][0] for profile in profiles]
        self.assertEqual(methods.count("ladrc"), 3)
        self.assertEqual(methods.count("pid"), 1)
        self.assertEqual(allocation["winner_slots"], 3)
        self.assertEqual(allocation["challenger_slots"], 1)

        elite = next(
            profile
            for profile in profiles
            if profile["controller_assignment"]["role"] == "elite"
        )
        self.assertEqual(elite["preferred_control_methods"], ["ladrc"])
        self.assertEqual(elite["parameter_seed_policy"]["mode"], "inherit")
        self.assertEqual(
            elite["parameter_seed_policy"]["source_candidate"],
            "candidate_02",
        )

        challenger = next(
            profile
            for profile in profiles
            if profile["controller_assignment"]["role"] == "challenger"
        )
        self.assertEqual(challenger["preferred_control_methods"], ["pid"])
        self.assertEqual(
            challenger["parameter_seed_policy"]["source_candidate"],
            "candidate_03",
        )
        self.assertEqual(
            challenger["parameter_seed_policy"]["mode"],
            "inherit_then_perturb",
        )

    def test_explicit_user_method_disables_cross_method_challenger(self):
        profiles, allocation = _apply_controller_method_allocation(
            self._profiles(),
            self._feedback(),
            "速度环采用 PID 控制器",
        )

        self.assertTrue(
            all(profile["preferred_control_methods"] == ["pid"] for profile in profiles)
        )
        self.assertEqual(allocation["mode"], "user_constraint")
        self.assertEqual(allocation["challenger_slots"], 0)


class RequirementRefinementControllerAllocationTests(unittest.TestCase):
    def test_refined_text_mentioning_both_methods_keeps_candidates_separate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            project_json = project_root / "project.json"
            project_json.write_text(json.dumps({"candidate_count": 2}), encoding="utf-8")
            candidate_dirs = []
            for index in (1, 2):
                candidate_dir = project_root / "candidates" / f"candidate_{index:02d}"
                candidate_dir.mkdir(parents=True)
                (candidate_dir / "candidate.json").write_text(
                    json.dumps({"candidate_id": candidate_dir.name}),
                    encoding="utf-8",
                )
                candidate_dirs.append(candidate_dir)

            class FakePanel:
                _pending_program_text = "请设计高速风机转速控制器"
                _program_requirement_before_refine = ""

                @staticmethod
                def _project_json_path():
                    return project_json

                @staticmethod
                def _candidate_dirs():
                    return candidate_dirs

                @staticmethod
                def _append_debug(*_args):
                    return None

                @staticmethod
                def _append_error(*_args):
                    raise AssertionError(_args)

            MainProgramPanel._update_project_json_requirement(
                FakePanel(),
                "首轮分别使用 PID 和 LADRC 候选方案进行转速控制比较。",
            )

            assigned_methods = []
            for candidate_dir in candidate_dirs:
                candidate = json.loads(
                    (candidate_dir / "candidate.json").read_text(encoding="utf-8")
                )
                assigned_methods.append(
                    candidate["design_profile"]["preferred_control_methods"]
                )
            self.assertEqual(assigned_methods, [["pid"], ["ladrc"]])

            common_profiles = json.loads(
                (project_root / "common" / "candidate_profiles.json").read_text(
                    encoding="utf-8"
                )
            )["profiles"]
            self.assertEqual(
                [profile["preferred_control_methods"] for profile in common_profiles],
                [["pid"], ["ladrc"]],
            )


if __name__ == "__main__":
    unittest.main()
