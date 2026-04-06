from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_json_field(value: Any, default: Any = None) -> Any:
    if not isinstance(value, str):
        return value if value is not None else default
    stripped = value.strip()
    if not stripped:
        return default
    if stripped in {"None", "null"}:
        return default
    if stripped[0] in "[{":
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return default if default is not None else value
    return value


def to_bool(value: Any) -> bool | None:
    if value in {None, "", "None"}:
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    return None


def to_int(value: Any) -> int | None:
    if value in {None, "", "None"}:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def to_float(value: Any) -> float | None:
    if value in {None, "", "None"}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_run_payload(run_dir: Path) -> dict[str, Any]:
    return {
        "metadata": read_json(run_dir / "run_metadata.json"),
        "event_rows": read_csv_rows(run_dir / "event_log.csv"),
        "trial_rows": read_csv_rows(run_dir / "trial_summary.csv"),
        "run_dir": run_dir,
    }


def expand_trial_rows(trial_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expanded_rows: list[dict[str, Any]] = []
    for row in trial_rows:
        expanded = dict(row)
        task_specific = parse_json_field(row.get("task_specific_data"), default={})
        stimulus_parameters = parse_json_field(row.get("stimulus_parameters"), default={})
        event_keys = parse_json_field(row.get("event_keys"), default=[])
        lsl_marker_codes = parse_json_field(row.get("lsl_marker_codes"), default=[])
        lpt_marker_codes = parse_json_field(row.get("lpt_marker_codes"), default=[])
        fnirs_marker_codes = parse_json_field(row.get("fnirs_marker_codes"), default=[])

        expanded["task_specific_data"] = task_specific
        expanded["stimulus_parameters"] = stimulus_parameters
        expanded["event_keys"] = event_keys
        expanded["lsl_marker_codes"] = lsl_marker_codes
        expanded["lpt_marker_codes"] = lpt_marker_codes
        expanded["fnirs_marker_codes"] = fnirs_marker_codes
        expanded["block"] = to_int(row.get("block"))
        expanded["trial_index"] = to_int(row.get("trial_index"))
        expanded["rt"] = to_float(row.get("rt"))
        expanded["stim_onset"] = to_float(row.get("stim_onset"))
        expanded["fixation_onset"] = to_float(row.get("fixation_onset"))
        expanded["response_time_abs"] = to_float(row.get("response_time_abs"))
        expanded["feedback_onset"] = to_float(row.get("feedback_onset"))
        expanded["iti_onset"] = to_float(row.get("iti_onset"))
        expanded["trial_end"] = to_float(row.get("trial_end"))
        expanded["timeout"] = to_bool(row.get("timeout")) is True
        correct = to_bool(row.get("correct"))
        expanded["correct"] = correct
        if isinstance(task_specific, dict):
            expanded.update(task_specific)
        expanded_rows.append(expanded)
    return expanded_rows