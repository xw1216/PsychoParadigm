import csv
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from paradigm.config import DEFAULT_CONFIG
from paradigm.runtime.logging_utils import EVENT_FIELDS, INVALID_NUMERIC, EventLogger, TrialLogger
from paradigm.runtime.logging_utils import write_metadata


class LoggingUtilsTests(unittest.TestCase):
    def test_trial_logger_serializes_extra_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "trial.csv"
            logger = TrialLogger(file_path)
            logger.log_trial({"participant": "P001", "session": "S01", "task": "doors", "block": 1, "trial_index": 1, "condition": "gain", "response": "left", "rt": 0.42, "custom_metric": 7})
            logger.close()

            with file_path.open("r", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(len(rows), 1)
            self.assertIn('"custom_metric": 7', rows[0]["task_specific_data"])

    def test_event_logger_increments_event_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "events.csv"
            logger = EventLogger(file_path)
            logger.log(abs_time=1.0, task_time=0.1, task="doors", block=1, trial=1, event_key="doors.choice.onset", event_code=12)
            logger.log(abs_time=2.0, task_time=0.2, task="doors", block=1, trial=1, event_key="doors.response.left", event_code=13)
            logger.close()

            with file_path.open("r", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual([row["event_index"] for row in rows], ["1", "2"])
            self.assertNotIn("description", EVENT_FIELDS)

    def test_event_logger_uses_invalid_sentinel_for_missing_flip_time(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "events.csv"
            logger = EventLogger(file_path)
            logger.log(abs_time=1.0, task_time=0.1, task="doors", block=1, trial=1, event_key="doors.choice.onset", event_code=12, flip_time=None)
            logger.close()

            with file_path.open("r", encoding="utf-8") as handle:
                row = next(csv.DictReader(handle))

            self.assertEqual(float(row["flip_time"]), INVALID_NUMERIC)

    def test_write_metadata_serializes_numpy_scalars(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "run_metadata.json"
            write_metadata(
                file_path,
                participant="P001",
                session="S01",
                task_name="doors",
                config=DEFAULT_CONFIG,
                started_at="2026-03-24T18:00:00.000",
                psychopy_version="2025.1",
                marker_status={"lsl_enabled": False},
                frame_rate_estimate=np.float64(75.0),
                window_info={"size": [np.int64(1920), np.int64(1080)], "color": np.array([-0.85, -0.85, -0.85])},
            )

            payload = json.loads(file_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["frame_rate_estimate"], 75.0)
            self.assertEqual(payload["window_info"]["size"], [1920, 1080])
            self.assertEqual(payload["window_info"]["color"], [-0.85, -0.85, -0.85])

    def test_write_metadata_keeps_utf8_characters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "run_metadata.json"
            write_metadata(
                file_path,
                participant="P001",
                session="S01",
                task_name="doors",
                config=DEFAULT_CONFIG,
                started_at="2026-03-24T18:00:00.000",
                psychopy_version="2025.1",
                marker_status={"label": "奖励"},
                frame_rate_estimate=75.0,
                window_info={"title": "反应过慢"},
            )

            text = file_path.read_text(encoding="utf-8")
            self.assertIn("奖励", text)
            self.assertIn("反应过慢", text)
            self.assertNotIn("\\u", text)
