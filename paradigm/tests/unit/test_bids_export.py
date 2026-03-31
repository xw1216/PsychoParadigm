import csv
import json
import tempfile
import unittest
from pathlib import Path

from paradigm.scripts.export_bids import build_bids_beh_rows, build_bids_event_rows, export_run_to_bids


class BIDSExportTests(unittest.TestCase):
    def test_build_bids_event_rows_uses_semantic_trial_type(self) -> None:
        event_rows = [
            {"task": "doors", "task_time": "0.5", "event_key": "doors.choice.onset", "event_code": "12", "block": "1", "trial": "1"},
            {"task": "doors", "task_time": "1.0", "event_key": "doors.feedback.gain", "event_code": "17", "block": "1", "trial": "1"},
        ]
        trial_rows = [{"task": "doors", "trial_index": "1", "rt": "0.4", "response": "left", "feedback": "gain", "correct": "None", "timeout": "False"}]
        rows = build_bids_event_rows(event_rows, trial_rows)
        self.assertEqual(rows[0]["event_key"], "doors.choice.onset")
        self.assertEqual(rows[0]["event_code"], 12)

    def test_build_bids_beh_rows_keeps_analysis_columns(self) -> None:
        rows = build_bids_beh_rows(
            [
                {
                    "stim_onset": "0.5",
                    "trial_end": "2.0",
                    "block": "1",
                    "trial_index": "1",
                    "condition": "left_0.2",
                    "rt": "0.6",
                    "response": "left",
                    "correct": "True",
                    "feedback": "Correct",
                    "timeout": "False",
                    "stimulus_parameters": '{"coherence": 0.2}',
                    "event_keys": '["rdm.motion.onset", "rdm.response.left"]',
                    "lsl_marker_codes": "[52, 53]",
                    "fnirs_marker_codes": "[4052, 4053]",
                    "task_specific_data": '{"exclude_trial": null}',
                }
            ]
        )
        self.assertEqual(rows[0]["condition"], "left_0.2")
        self.assertEqual(rows[0]["duration"], 1.5)
        self.assertIn("exclude_trial", rows[0]["task_specific_data"])

    def test_export_run_to_bids_writes_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run_dir = Path(tmp_dir) / "20260324_120000"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "run_metadata.json").write_text(
                json.dumps(
                    {
                        "participant": "P001",
                        "session": "S01",
                        "task": "doors",
                        "event_codebook": {"doors": {"doors.choice.onset": {"event_code": 12, "description": "Door choice screen onset."}}},
                        "event_codebook_schema": {"entry_fields": {"event_code": {"type": "integer"}}},
                    }
                ),
                encoding="utf-8",
            )
            with (run_dir / "event_log.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["task", "task_time", "event_key", "event_code", "block", "trial"])
                writer.writeheader()
                writer.writerow({"task": "doors", "task_time": "0.5", "event_key": "doors.choice.onset", "event_code": "12", "block": "1", "trial": "1"})
            with (run_dir / "trial_summary.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["task", "trial_index", "stim_onset", "trial_end", "condition", "rt", "response", "correct", "feedback", "timeout", "stimulus_parameters", "event_keys", "lsl_marker_codes", "fnirs_marker_codes", "task_specific_data"])
                writer.writeheader()
                writer.writerow({"task": "doors", "trial_index": "1", "stim_onset": "0.5", "trial_end": "1.5", "condition": "gain", "rt": "0.4", "response": "left", "correct": "None", "feedback": "gain", "timeout": "False", "stimulus_parameters": "{}", "event_keys": '["doors.choice.onset"]', "lsl_marker_codes": "[12]", "fnirs_marker_codes": "[]", "task_specific_data": "{}"})

            output = export_run_to_bids(run_dir, Path(tmp_dir) / "bids")
            self.assertTrue(output["events_tsv"].exists())
            self.assertTrue(output["beh_tsv"].exists())
            self.assertTrue((Path(tmp_dir) / "bids" / "dataset_description.json").exists())
            beh_json = json.loads(output["beh_json"].read_text(encoding="utf-8"))
            self.assertIn("Fields", beh_json["task_specific_data"])
            self.assertIn("feedback_type", beh_json["task_specific_data"]["Fields"])
            self.assertIn("ground-truth event source", beh_json["event_keys"]["Description"])