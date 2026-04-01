from __future__ import annotations

import json
from typing import Any


def _to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_codes(value: Any) -> list[int]:
    if value is None:
        return []
    if isinstance(value, list):
        return [int(item) for item in value if item not in (None, "")]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return []
        return _normalize_codes(parsed)
    return [int(value)]


def validate_trial_temporal_consistency(trial_row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    stim_onset = trial_row.get("stim_onset")
    response_time_abs = trial_row.get("response_time_abs")
    feedback_onset = trial_row.get("feedback_onset")
    timeout = trial_row.get("timeout")

    if stim_onset is not None and response_time_abs is not None and response_time_abs < stim_onset:
        errors.append("response_time_abs precedes stim_onset")
    if response_time_abs is not None and feedback_onset is not None and feedback_onset < response_time_abs:
        errors.append("feedback_onset precedes response_time_abs")
    if stim_onset is not None and feedback_onset is not None and feedback_onset < stim_onset:
        errors.append("feedback_onset precedes stim_onset")
    if timeout and trial_row.get("response") not in (None, ""):
        errors.append("timeout trial should not have a response")
    return errors


def validate_event_trial_consistency(event_rows: list[dict[str, Any]], trial_rows: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    events_by_trial: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in event_rows:
        trial = _to_int(row.get("trial"))
        task = row.get("task")
        if trial is None or task in (None, ""):
            continue
        events_by_trial.setdefault((str(task), trial), []).append(row)

    for trial_row in trial_rows:
        task = trial_row.get("task")
        trial_index = _to_int(trial_row.get("trial_index"))
        if task in (None, "") or trial_index is None:
            continue
        key = (str(task), trial_index)
        matching_events = events_by_trial.get(key, [])
        if not matching_events:
            errors.append(f"Missing events for {key[0]} trial {key[1]}")
            continue
        event_codes = {int(row["event_code"]) for row in matching_events if row.get("event_code") not in (None, "")}
        trial_codes = set(_normalize_codes(trial_row.get("lsl_marker_codes")))
        if not trial_codes.issubset(event_codes):
            errors.append(f"LSL marker codes do not match event log for {key[0]} trial {key[1]}")
    return errors
