import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from paradigm.analysis.log_audit import AUDIT_REPORT_NAME, audit_run_directory
from paradigm.config import DEFAULT_CONFIG
from paradigm.data.logging import EVENT_FIELDS, TRIAL_FIELDS
from paradigm.runtime.base_experiment import BaseExperiment


class LogAuditTests(unittest.TestCase):
    def _write_run_files(self, run_dir: Path, *, mixed_clock: bool, invalid_lpt_codes: bool, mixed_event_clock: bool = False) -> None:
        config_snapshot = copy.deepcopy(DEFAULT_CONFIG.snapshot())
        config_snapshot["practice"]["enabled"] = True
        config_snapshot["fnirs"]["enable_namespace"] = False
        config_snapshot["doors"]["blocks"] = 1
        config_snapshot["doors"]["trials_per_block"] = 1

        metadata = {
            "participant": "P001",
            "session": "S01",
            "task": "doors",
            "frame_rate_estimate": 75.0,
            "marker_status": {
                "lsl_enabled": True,
                "lpt_enabled": False,
                "fnirs_enabled": False,
            },
            "config_snapshot": config_snapshot,
        }
        (run_dir / "run_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        event_rows = [
            {"event_index": 1, "iso_time": "2026-04-06T21:00:00.000", "abs_time": 0.00, "task_time": 0.00, "task": "doors", "block": "", "trial": "", "event_key": "doors.experiment.start", "event_code": 25, "flip_time": -1.0, "lsl_sent": True, "lpt_sent": False, "fnirs_sent": False, "extra_metadata": "{}"},
            {"event_index": 2, "iso_time": "2026-04-06T21:00:00.010", "abs_time": 0.01, "task_time": 0.01, "task": "doors", "block": 1, "trial": "", "event_key": "doors.block.start", "event_code": 21, "flip_time": -1.0, "lsl_sent": True, "lpt_sent": False, "fnirs_sent": False, "extra_metadata": "{}"},
            {"event_index": 3, "iso_time": "2026-04-06T21:00:00.500", "abs_time": 0.50, "task_time": 0.50, "task": "doors", "block": 1, "trial": 1, "event_key": "doors.fixation.onset", "event_code": 11, "flip_time": 0.50, "lsl_sent": True, "lpt_sent": False, "fnirs_sent": False, "extra_metadata": "{}"},
            {"event_index": 4, "iso_time": "2026-04-06T21:00:01.000", "abs_time": 1.00, "task_time": 1.00, "task": "doors", "block": 1, "trial": 1, "event_key": "doors.choice.onset", "event_code": 12, "flip_time": 1.00, "lsl_sent": True, "lpt_sent": False, "fnirs_sent": False, "extra_metadata": "{}"},
            {"event_index": 5, "iso_time": "2026-04-06T21:00:01.400", "abs_time": 1.40, "task_time": 1.40, "task": "doors", "block": 1, "trial": 1, "event_key": "doors.response.left", "event_code": 13, "flip_time": -1.0, "lsl_sent": True, "lpt_sent": False, "fnirs_sent": False, "extra_metadata": "{}"},
            {"event_index": 6, "iso_time": "2026-04-06T21:00:01.420", "abs_time": 1.42, "task_time": 1.42, "task": "doors", "block": 1, "trial": 1, "event_key": "doors.post_choice_delay.onset", "event_code": 16, "flip_time": 1.42, "lsl_sent": True, "lpt_sent": False, "fnirs_sent": False, "extra_metadata": "{}"},
            {"event_index": 7, "iso_time": "2026-04-06T21:00:01.920", "abs_time": 1.92, "task_time": 1.92, "task": "doors", "block": 1, "trial": 1, "event_key": "doors.feedback.gain", "event_code": 17, "flip_time": 1.92, "lsl_sent": True, "lpt_sent": False, "fnirs_sent": False, "extra_metadata": "{}"},
            {"event_index": 8, "iso_time": "2026-04-06T21:00:02.920", "abs_time": 2.92, "task_time": 2.92, "task": "doors", "block": 1, "trial": 1, "event_key": "doors.iti.onset", "event_code": 19, "flip_time": 2.92, "lsl_sent": True, "lpt_sent": False, "fnirs_sent": False, "extra_metadata": "{}"},
            {"event_index": 9, "iso_time": "2026-04-06T21:00:03.820", "abs_time": 3.82, "task_time": 3.82, "task": "doors", "block": 1, "trial": "", "event_key": "doors.block.end", "event_code": 22, "flip_time": -1.0, "lsl_sent": True, "lpt_sent": False, "fnirs_sent": False, "extra_metadata": "{}"},
            {"event_index": 10, "iso_time": "2026-04-06T21:00:03.830", "abs_time": 3.83, "task_time": 3.83, "task": "doors", "block": "", "trial": "", "event_key": "doors.experiment.end", "event_code": 26, "flip_time": -1.0, "lsl_sent": True, "lpt_sent": False, "fnirs_sent": False, "extra_metadata": "{}"},
        ]
        if mixed_event_clock:
            event_rows[3]["task_time"] = 0.70
            event_rows[3]["flip_time"] = 1.70
        with (run_dir / "event_log.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=EVENT_FIELDS)
            writer.writeheader()
            writer.writerows(event_rows)

        response_time_abs = 0.70 if mixed_clock else 1.40
        lpt_marker_codes = [12, 13, 16, 17, 19] if invalid_lpt_codes else []
        trial_row = {
            "participant": "P001",
            "session": "S01",
            "task": "doors",
            "block": 1,
            "trial_index": 1,
            "condition": "gain",
            "stimulus_parameters": json.dumps({"door_positions": {"left": -0.25, "right": 0.25}, "post_choice_delay_s": 0.5}, ensure_ascii=False),
            "response": "left",
            "rt": 0.4,
            "correct": "",
            "feedback": "gain",
            "timeout": False,
            "fixation_onset": 0.50,
            "stim_onset": 1.00,
            "response_time_abs": response_time_abs,
            "feedback_onset": 1.92,
            "iti_onset": 2.92,
            "trial_end": 3.82,
            "lsl_marker_codes": json.dumps([12, 13, 16, 17, 19], ensure_ascii=False),
            "lpt_marker_codes": json.dumps(lpt_marker_codes, ensure_ascii=False),
            "event_keys": json.dumps(["doors.choice.onset", "doors.response.left", "doors.post_choice_delay.onset", "doors.feedback.gain", "doors.iti.onset"], ensure_ascii=False),
            "fnirs_marker_codes": json.dumps([], ensure_ascii=False),
            "task_specific_data": json.dumps({"post_choice_delay_onset": 1.42}, ensure_ascii=False),
        }
        with (run_dir / "trial_summary.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=TRIAL_FIELDS)
            writer.writeheader()
            writer.writerow(trial_row)

        with (run_dir / "frame_intervals.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["frame_index", "interval_s"])
            writer.writeheader()
            writer.writerow({"frame_index": 1, "interval_s": 1 / 75.0})
            writer.writerow({"frame_index": 2, "interval_s": 1 / 75.0})
            writer.writerow({"frame_index": 3, "interval_s": 1 / 75.0})

    def test_audit_run_directory_passes_for_consistent_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run_dir = Path(tmp_dir)
            self._write_run_files(run_dir, mixed_clock=False, invalid_lpt_codes=False)
            report = audit_run_directory(run_dir)

        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["checks"]["phase_timing"]["status"], "pass")
        self.assertEqual(report["checks"]["marker_semantics"]["status"], "pass")

    def test_audit_run_directory_flags_mixed_clock_and_invalid_lpt_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run_dir = Path(tmp_dir)
            self._write_run_files(run_dir, mixed_clock=True, invalid_lpt_codes=True)
            report = audit_run_directory(run_dir)

        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["checks"]["phase_timing"]["status"], "fail")
        self.assertEqual(report["checks"]["marker_semantics"]["status"], "fail")

    def test_audit_run_directory_flags_event_clock_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run_dir = Path(tmp_dir)
            self._write_run_files(run_dir, mixed_clock=False, invalid_lpt_codes=False, mixed_event_clock=True)
            report = audit_run_directory(run_dir)

        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["checks"]["event_clock_alignment"]["status"], "fail")

    def test_finalize_runs_practice_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            experiment = BaseExperiment.__new__(BaseExperiment)
            experiment.task_name = "doors"
            experiment.paths = SimpleNamespace(run_dir=Path(tmp_dir), frame_interval_path=Path(tmp_dir) / "frame_intervals.csv")
            experiment.config = SimpleNamespace(
                screen=SimpleNamespace(record_frame_intervals=False, target_frame_rate=60.0),
                practice=SimpleNamespace(enabled=True),
                logging=SimpleNamespace(dropped_frame_factor=1.5),
            )
            experiment.finished_at = None
            experiment.frame_rate_estimate = 75.0
            experiment.window = SimpleNamespace(frameIntervals=[], close=Mock())
            experiment.event_logger = SimpleNamespace(close=Mock())
            experiment.trial_logger = SimpleNamespace(close=Mock())
            experiment.marker_manager = SimpleNamespace(close=Mock())
            experiment.eye_tracker_manager = SimpleNamespace(close=Mock())
            experiment._write_metadata_snapshot = Mock()

            with patch("paradigm.analysis.log_audit.audit_run_directory", return_value={"status": "pass"}) as audit_run, patch(
                "paradigm.analysis.log_audit.write_audit_report",
                return_value=Path(tmp_dir) / AUDIT_REPORT_NAME,
            ) as write_report, patch("paradigm.runtime.base_experiment.core.quit"):
                BaseExperiment.finalize(experiment)

        audit_run.assert_called_once_with(Path(tmp_dir))
        write_report.assert_called_once()
