from __future__ import annotations

import csv
import json
import platform
import sys
from pathlib import Path
from typing import Any

from paradigm.config import AppConfig
from paradigm.utils.paths import ensure_directory
from paradigm.utils.serialization import make_json_safe, to_json_string
from paradigm.utils.time import iso_timestamp


EVENT_FIELDS = [
    "event_index",
    "iso_time",
    "abs_time",
    "task_time",
    "task",
    "block",
    "trial",
    "event_key",
    "event_code",
    "flip_time",
    "lsl_sent",
    "lpt_sent",
    "fnirs_sent",
    "extra_metadata",
]


TRIAL_FIELDS = [
    "participant",
    "session",
    "task",
    "block",
    "trial_index",
    "condition",
    "stimulus_parameters",
    "response",
    "rt",
    "correct",
    "feedback",
    "timeout",
    "fixation_onset",
    "stim_onset",
    "response_time_abs",
    "feedback_onset",
    "iti_onset",
    "trial_end",
    "lsl_marker_codes",
    "lpt_marker_codes",
    "event_keys",
    "fnirs_marker_codes",
    "task_specific_data",
]


INVALID_NUMERIC = -1.0


class CSVLogger:
    def __init__(self, file_path: Path, fieldnames: list[str]) -> None:
        ensure_directory(file_path.parent)
        self.file = file_path.open("w", newline="", encoding="utf-8")
        self.writer = csv.DictWriter(self.file, fieldnames=fieldnames, extrasaction="ignore")
        self.writer.writeheader()

    def write_row(self, row: dict[str, Any], *, flush: bool) -> None:
        serialized: dict[str, Any] = {}
        for key, value in row.items():
            if key == "flip_time" and value is None:
                serialized[key] = INVALID_NUMERIC
            elif isinstance(value, (dict, list, tuple)):
                serialized[key] = to_json_string(value)
            else:
                serialized[key] = value
        self.writer.writerow(serialized)
        if flush:
            self.file.flush()

    def close(self) -> None:
        self.file.flush()
        self.file.close()


class EventLogger:
    def __init__(self, file_path: Path, flush_every_event: bool = True) -> None:
        self._csv = CSVLogger(file_path=file_path, fieldnames=EVENT_FIELDS)
        self._counter = 0
        self.flush_every_event = flush_every_event

    def log(
        self,
        *,
        abs_time: float,
        task_time: float,
        task: str,
        block: int | None,
        trial: int | None,
        event_key: str,
        event_code: int | None = None,
        flip_time: float | None = None,
        lsl_sent: bool | None = None,
        lpt_sent: bool | None = None,
        fnirs_sent: bool | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> None:
        self._counter += 1
        self._csv.write_row(
            {
                "event_index": self._counter,
                "iso_time": iso_timestamp(),
                "abs_time": abs_time,
                "task_time": task_time,
                "task": task,
                "block": block,
                "trial": trial,
                "event_key": event_key,
                "event_code": event_code,
                "flip_time": flip_time,
                "lsl_sent": lsl_sent,
                "lpt_sent": lpt_sent,
                "fnirs_sent": fnirs_sent,
                "extra_metadata": extra_metadata or {},
            },
            flush=self.flush_every_event,
        )

    def close(self) -> None:
        self._csv.close()


class TrialLogger:
    def __init__(self, file_path: Path, flush_every_event: bool = True) -> None:
        self._csv = CSVLogger(file_path=file_path, fieldnames=TRIAL_FIELDS)
        self.flush_every_event = flush_every_event

    def log_trial(self, row: dict[str, Any]) -> None:
        base_row = {field: row.get(field) for field in TRIAL_FIELDS}
        extra = {key: value for key, value in row.items() if key not in TRIAL_FIELDS}
        if extra:
            existing_task_specific = base_row.get("task_specific_data")
            merged_task_specific: dict[str, Any] = {}
            if isinstance(existing_task_specific, dict):
                merged_task_specific.update(existing_task_specific)
            elif existing_task_specific not in (None, ""):
                merged_task_specific["legacy_task_specific_data"] = existing_task_specific
            merged_task_specific.update(extra)
            base_row["task_specific_data"] = merged_task_specific
        self._csv.write_row(base_row, flush=self.flush_every_event)

    def close(self) -> None:
        self._csv.close()


def write_metadata(
    file_path: Path,
    *,
    participant: str,
    session: str,
    task_name: str,
    config: AppConfig,
    started_at: str,
    psychopy_version: str,
    marker_status: dict[str, Any],
    frame_rate_estimate: float | None,
    window_info: dict[str, Any],
    extra: dict[str, Any] | None = None,
) -> None:
    ensure_directory(file_path.parent)
    payload = {
        "participant": participant,
        "session": session,
        "task": task_name,
        "started_at": started_at,
        "python_version": sys.version,
        "platform": platform.platform(),
        "psychopy_version": psychopy_version,
        "frame_rate_estimate": frame_rate_estimate,
        "window_info": window_info,
        "marker_status": marker_status,
        "config_snapshot": config.snapshot(),
    }
    if extra:
        payload.update(extra)
    file_path.write_text(json.dumps(make_json_safe(payload), indent=2, ensure_ascii=False), encoding="utf-8")


def write_frame_intervals(file_path: Path, frame_intervals: list[float]) -> None:
    ensure_directory(file_path.parent)
    with file_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["frame_index", "interval_s"])
        writer.writeheader()
        for index, interval in enumerate(frame_intervals, start=1):
            writer.writerow({"frame_index": index, "interval_s": interval})