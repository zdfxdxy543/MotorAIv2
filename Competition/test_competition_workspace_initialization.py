import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from Competition.competition_workspace import init_candidates


class CandidateInitializationTests(unittest.TestCase):
    def test_init_copies_all_required_projects_to_every_candidate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            template = root / "template"
            (template / "src").mkdir(parents=True)
            (template / "project" / "simulate").mkdir(parents=True)
            (template / "project" / "f280049c").mkdir(parents=True)
            (template / "project" / "f280049c_TIBoard_motorai").mkdir(parents=True)
            (template / "src" / "ctl_main.c").write_text("source", encoding="utf-8")
            (template / "project" / "simulate" / "simulate.txt").write_text(
                "simulate",
                encoding="utf-8",
            )
            (template / "project" / "f280049c" / "f280049c.txt").write_text(
                "f280049c",
                encoding="utf-8",
            )
            (template / "project" / "f280049c_TIBoard_motorai" / "hardware.txt").write_text(
                "hardware",
                encoding="utf-8",
            )

            project_root = root / "output"
            project_root.mkdir()
            project_json = project_root / "project.json"
            project_json.write_text(
                json.dumps({"template_project_path": str(template)}),
                encoding="utf-8",
            )

            with patch(
                "Competition.competition_workspace.configure_candidate_optimize",
                return_value={},
            ):
                init_candidates(project_json, 2, template_root=template)

                for candidate_id in ("candidate_01", "candidate_02"):
                    candidate_root = project_root / "candidates" / candidate_id
                    self.assertEqual(
                        (candidate_root / "project" / "simulate" / "simulate.txt").read_text(
                            encoding="utf-8"
                        ),
                        "simulate",
                    )
                    self.assertEqual(
                        (candidate_root / "project" / "f280049c" / "f280049c.txt").read_text(
                            encoding="utf-8"
                        ),
                        "f280049c",
                    )
                    self.assertEqual(
                        (
                            candidate_root
                            / "project"
                            / "f280049c_TIBoard_motorai"
                            / "hardware.txt"
                        ).read_text(encoding="utf-8"),
                        "hardware",
                    )

                hardware_file = (
                    project_root
                    / "candidates"
                    / "candidate_01"
                    / "project"
                    / "f280049c_TIBoard_motorai"
                    / "hardware.txt"
                )
                hardware_file.write_text("changed", encoding="utf-8")
                init_candidates(project_json, 2, force=True, template_root=template)
                self.assertEqual(hardware_file.read_text(encoding="utf-8"), "hardware")


if __name__ == "__main__":
    unittest.main()
