from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

from paradigm.contracts.validation import validate_event_trial_consistency, validate_trial_temporal_consistency
from paradigm.data.run_io import expand_trial_rows, load_run_payload, read_csv_rows, to_bool, to_float
from paradigm.utils.time import iso_timestamp


AUDIT_REPORT_NAME = "log_audit.json"


def _build_event_rows_by_trial(event_rows: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    events_by_trial: dict[int, list[dict[str, Any]]] = {}
    for row in event_rows:
        raw_trial = row.get("trial")
        if raw_trial in (None, ""):
            continue
        trial_index = int(raw_trial)
        events_by_trial.setdefault(trial_index, []).append(row)
    for rows in events_by_trial.values():
        rows.sort(key=lambda row: int(row.get("event_index") or 0))
    return events_by_trial


def _frame_rate_hz(metadata: dict[str, Any]) -> float:
    estimate = metadata.get("frame_rate_estimate")
    if estimate not in (None, ""):
        return float(estimate)
    return float(metadata["config_snapshot"]["screen"]["target_frame_rate"])


def _frame_tolerance_s(metadata: dict[str, Any]) -> float:
    return 1.5 / _frame_rate_hz(metadata)


def _stage_duration_tolerance_s(metadata: dict[str, Any]) -> float:
    return 2.5 / _frame_rate_hz(metadata)


def _response_tolerance_s(metadata: dict[str, Any]) -> float:
    return max(0.01, _frame_tolerance_s(metadata))


def _is_core_trial_event(event_key: str) -> bool:
    if event_key.startswith("system."):
        return False
    if event_key.endswith(".aoi.transition"):
        return False
    if ".block." in event_key or ".break." in event_key or ".experiment." in event_key:
        return False
    return True


def _feedback_event_key(task_name: str, trial_row: dict[str, Any]) -> str | None:
    feedback = trial_row.get("feedback")
    if task_name == "doors":
        return None if feedback in (None, "") else f"doors.feedback.{feedback}"
    if task_name == "prl":
        return {
            "reward": "prl.feedback.reward",
            "no_reward": "prl.feedback.no_reward",
            "timeout": "prl.feedback.timeout",
        }.get(str(feedback))
    if task_name == "rdm":
        return {
            "correct": "rdm.feedback.correct",
            "error": "rdm.feedback.error",
            "timeout": "rdm.feedback.timeout",
        }.get(str(feedback))
    return None


def _response_event_key(task_name: str, trial_row: dict[str, Any]) -> str:
    if trial_row.get("timeout"):
        return f"{task_name}.response.timeout"
    return f"{task_name}.response.{trial_row['response']}"


def _expected_trial_sequence(task_name: str, trial_row: dict[str, Any]) -> list[str]:
    sequence: list[str] = []
    if task_name == "prl" and bool(trial_row.get("is_reversal_boundary")):
        sequence.append("prl.reversal.boundary")

    if task_name == "doors":
        sequence.extend(
            [
                "doors.fixation.onset",
                "doors.choice.onset",
                _response_event_key(task_name, trial_row),
                "doors.post_choice_delay.onset",
                _feedback_event_key(task_name, trial_row),
                "doors.iti.onset",
            ]
        )
        return [item for item in sequence if item is not None]

    if task_name == "prl":
        sequence.extend(["prl.fixation.onset", "prl.choice.onset", _response_event_key(task_name, trial_row)])
        if not trial_row.get("timeout"):
            sequence.append("prl.post_choice_delay.onset")
        sequence.extend([_feedback_event_key(task_name, trial_row), "prl.iti.onset"])
        return [item for item in sequence if item is not None]

    if task_name == "rdm":
        sequence.extend(
            [
                "rdm.fixation.onset",
                "rdm.premotion.onset",
                "rdm.motion.onset",
                _response_event_key(task_name, trial_row),
            ]
        )
        feedback_event = _feedback_event_key(task_name, trial_row)
        if feedback_event is not None:
            sequence.append(feedback_event)
        sequence.extend(["rdm.post_response_blank.onset", "rdm.iti.onset"])
    return [item for item in sequence if item is not None]


def _summarize_values(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    return {
        "count": len(values),
        "min_s": min(values),
        "max_s": max(values),
        "mean_s": statistics.mean(values),
    }


def _duration_issue(
    *,
    issues: list[dict[str, Any]],
    trial_index: int,
    stage: str,
    observed_s: float,
    expected: float | tuple[float, float],
    tolerance_s: float,
) -> None:
    if isinstance(expected, tuple):
        lower, upper = expected
        if observed_s < lower - tolerance_s or observed_s > upper + tolerance_s:
            issues.append(
                {
                    "trial": trial_index,
                    "stage": stage,
                    "observed_s": observed_s,
                    "expected_range_s": [lower, upper],
                    "tolerance_s": tolerance_s,
                }
            )
        return
    if abs(observed_s - expected) > tolerance_s:
        issues.append(
            {
                "trial": trial_index,
                "stage": stage,
                "observed_s": observed_s,
                "expected_s": expected,
                "tolerance_s": tolerance_s,
            }
        )


def _timing_stage_values(task_name: str, trial_row: dict[str, Any]) -> dict[str, float]:
    if task_name == "doors":
        return {
            "fixation": trial_row["stim_onset"] - trial_row["fixation_onset"],
            "post_choice_delay": trial_row["feedback_onset"] - trial_row["post_choice_delay_onset"],
            "feedback": trial_row["iti_onset"] - trial_row["feedback_onset"],
            "iti": trial_row["trial_end"] - trial_row["iti_onset"],
        }
    if task_name == "prl":
        values = {
            "fixation": trial_row["stim_onset"] - trial_row["fixation_onset"],
            "feedback": trial_row["iti_onset"] - trial_row["feedback_onset"],
            "iti": trial_row["trial_end"] - trial_row["iti_onset"],
        }
        if trial_row.get("post_choice_delay_onset") is not None:
            values["post_choice_delay"] = trial_row["feedback_onset"] - trial_row["post_choice_delay_onset"]
        return values
    values = {
        "fixation": trial_row["premotion_onset"] - trial_row["fixation_onset"],
        "premotion": trial_row["stim_onset"] - trial_row["premotion_onset"],
        "post_response_blank": trial_row["iti_onset"] - trial_row["post_response_blank_onset"],
        "iti": trial_row["trial_end"] - trial_row["iti_onset"],
    }
    if trial_row.get("feedback_onset") is not None:
        values["feedback"] = trial_row["post_response_blank_onset"] - trial_row["feedback_onset"]
    return values


def _timing_targets(task_name: str, metadata: dict[str, Any]) -> dict[str, float | tuple[float, float]]:
    config_snapshot = metadata["config_snapshot"]
    if task_name == "doors":
        return {
            "fixation": float(config_snapshot["doors"]["fixation_s"]),
            "post_choice_delay": float(config_snapshot["doors"]["post_choice_delay_s"]),
            "feedback": float(config_snapshot["doors"]["feedback_s"]),
            "iti": tuple(float(value) for value in config_snapshot["doors"]["iti_range_s"]),
        }
    if task_name == "prl":
        return {
            "fixation": float(config_snapshot["prl"]["fixation_s"]),
            "post_choice_delay": tuple(float(value) for value in config_snapshot["prl"]["post_choice_delay_range_s"]),
            "feedback": float(config_snapshot["prl"]["feedback_s"]),
            "iti": tuple(float(value) for value in config_snapshot["prl"]["iti_range_s"]),
        }
    return {
        "fixation": float(config_snapshot["rdm"]["fixation_s"]),
        "premotion": float(config_snapshot["rdm"]["premotion_s"]),
        "feedback": float(config_snapshot["rdm"]["feedback_s"]),
        "post_response_blank": float(config_snapshot["rdm"]["post_response_blank_s"]),
        "iti": tuple(float(value) for value in config_snapshot["rdm"]["iti_range_s"]),
    }


def _fnirs_code_for(task_name: str, metadata: dict[str, Any], event_code: int) -> int | None:
    fnirs_config = metadata["config_snapshot"].get("fnirs", {})
    if not fnirs_config.get("enable_namespace"):
        return None
    task_offset = int(fnirs_config.get("task_offsets", {}).get(task_name, 0))
    prefix = int(fnirs_config.get("prefix", 40))
    return prefix * 100 + task_offset + int(event_code)


def _check_event_completeness(
    *,
    task_name: str,
    metadata: dict[str, Any],
    event_rows: list[dict[str, Any]],
    trial_rows: list[dict[str, Any]],
    events_by_trial: dict[int, list[dict[str, Any]]],
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    task_event_keys = [str(row["event_key"]) for row in event_rows if str(row.get("task")) == task_name]
    if task_event_keys.count(f"{task_name}.experiment.start") != 1:
        issues.append({"issue": "experiment_start_count", "count": task_event_keys.count(f"{task_name}.experiment.start")})
    if task_event_keys.count(f"{task_name}.experiment.end") != 1:
        issues.append({"issue": "experiment_end_count", "count": task_event_keys.count(f"{task_name}.experiment.end")})

    observed_blocks = sorted({int(row["block"]) for row in trial_rows if row.get("block") is not None})
    for block in observed_blocks:
        if task_event_keys.count(f"{task_name}.block.start") < len(observed_blocks):
            break
    block_start_count = task_event_keys.count(f"{task_name}.block.start")
    block_end_count = task_event_keys.count(f"{task_name}.block.end")
    if block_start_count != len(observed_blocks):
        issues.append({"issue": "block_start_count", "expected": len(observed_blocks), "observed": block_start_count})
    if block_end_count != len(observed_blocks):
        issues.append({"issue": "block_end_count", "expected": len(observed_blocks), "observed": block_end_count})

    break_start_count = task_event_keys.count(f"{task_name}.break.start")
    break_end_count = task_event_keys.count(f"{task_name}.break.end")
    if break_start_count != break_end_count:
        issues.append({"issue": "break_count_mismatch", "break_start": break_start_count, "break_end": break_end_count})

    for row in trial_rows:
        trial_index = int(row["trial_index"])
        actual_sequence = [
            str(event_row["event_key"])
            for event_row in events_by_trial.get(trial_index, [])
            if _is_core_trial_event(str(event_row["event_key"]))
        ]
        expected_sequence = _expected_trial_sequence(task_name, row)
        if actual_sequence != expected_sequence:
            issues.append(
                {
                    "trial": trial_index,
                    "issue": "trial_event_sequence",
                    "expected": expected_sequence,
                    "observed": actual_sequence,
                }
            )

    return {
        "status": "fail" if issues else "pass",
        "issue_count": len(issues),
        "issues": issues[:20],
    }


def _check_phase_timing(*, task_name: str, metadata: dict[str, Any], trial_rows: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    stage_samples: dict[str, list[float]] = {}
    timing_targets = _timing_targets(task_name, metadata)
    duration_tolerance_s = _stage_duration_tolerance_s(metadata)
    response_tolerance_s = _response_tolerance_s(metadata)

    for row in trial_rows:
        trial_index = int(row["trial_index"])
        temporal_errors = validate_trial_temporal_consistency(row)
        if temporal_errors:
            issues.append({"trial": trial_index, "issue": "temporal_consistency", "errors": temporal_errors})

        stim_onset = row.get("stim_onset")
        response_time_abs = row.get("response_time_abs")
        rt = row.get("rt")
        if stim_onset is not None and response_time_abs is not None and rt is not None:
            delta = (response_time_abs - stim_onset) - rt
            if abs(delta) > response_tolerance_s:
                issues.append(
                    {
                        "trial": trial_index,
                        "issue": "response_rt_mismatch",
                        "observed_delta_s": delta,
                        "tolerance_s": response_tolerance_s,
                    }
                )

        for stage_name, observed_value in _timing_stage_values(task_name, row).items():
            stage_samples.setdefault(stage_name, []).append(observed_value)
            expected = timing_targets[stage_name]
            _duration_issue(
                issues=issues,
                trial_index=trial_index,
                stage=stage_name,
                observed_s=observed_value,
                expected=expected,
                tolerance_s=duration_tolerance_s,
            )

    return {
        "status": "fail" if issues else "pass",
        "issue_count": len(issues),
        "issues": issues[:20],
        "tolerance_s": duration_tolerance_s,
        "response_tolerance_s": response_tolerance_s,
        "stage_summary": {stage_name: _summarize_values(values) for stage_name, values in stage_samples.items()},
    }


def _check_event_clock_alignment(*, task_name: str, metadata: dict[str, Any], event_rows: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    tolerance_s = _response_tolerance_s(metadata)
    task_event_rows = [row for row in event_rows if str(row.get("task")) == task_name]
    clock_offsets = [
        float(abs_time) - float(task_time)
        for row in task_event_rows
        if (abs_time := to_float(row.get("abs_time"))) is not None and (task_time := to_float(row.get("task_time"))) is not None
    ]
    reference_offset = statistics.median(clock_offsets) if clock_offsets else None

    for row in task_event_rows:
        event_index = int(row.get("event_index") or 0)
        event_key = str(row.get("event_key") or "")
        abs_time = to_float(row.get("abs_time"))
        task_time = to_float(row.get("task_time"))
        flip_time = to_float(row.get("flip_time"))

        if reference_offset is not None and abs_time is not None and task_time is not None:
            observed_offset = abs_time - task_time
            if abs(observed_offset - reference_offset) > tolerance_s:
                issues.append(
                    {
                        "event_index": event_index,
                        "event_key": event_key,
                        "issue": "abs_task_clock_offset_mismatch",
                        "observed_offset_s": observed_offset,
                        "expected_offset_s": reference_offset,
                        "tolerance_s": tolerance_s,
                    }
                )

        if flip_time is not None and flip_time >= 0 and abs_time is not None and abs(flip_time - abs_time) > tolerance_s:
            issues.append(
                {
                    "event_index": event_index,
                    "event_key": event_key,
                    "issue": "flip_time_abs_time_mismatch",
                    "flip_time_s": flip_time,
                    "abs_time_s": abs_time,
                    "tolerance_s": tolerance_s,
                }
            )

    return {
        "status": "fail" if issues else "pass",
        "issue_count": len(issues),
        "issues": issues[:20],
        "tolerance_s": tolerance_s,
        "reference_offset_s": reference_offset,
    }


def _check_frame_intervals(*, run_dir: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    frame_rows = read_csv_rows(run_dir / metadata["config_snapshot"]["data"]["frame_interval_name"])
    intervals = [float(row["interval_s"]) for row in frame_rows if row.get("interval_s") not in (None, "")]
    threshold_s = metadata["config_snapshot"]["logging"]["dropped_frame_factor"] / _frame_rate_hz(metadata)
    dropped = [interval for interval in intervals if interval > threshold_s]
    if not intervals:
        return {
            "status": "warning",
            "issue_count": 1,
            "issues": [{"issue": "missing_frame_intervals"}],
            "threshold_s": threshold_s,
            "dropped_count": 0,
        }

    dropped_ratio = len(dropped) / len(intervals)
    if not dropped:
        status = "pass"
    elif dropped_ratio <= 0.005:
        status = "warning"
    else:
        status = "fail"

    issues = []
    if dropped:
        issues.append(
            {
                "issue": "dropped_frames_detected",
                "dropped_count": len(dropped),
                "frame_count": len(intervals),
                "ratio": dropped_ratio,
                "examples_s": dropped[:10],
            }
        )

    return {
        "status": status,
        "issue_count": len(issues),
        "issues": issues,
        "threshold_s": threshold_s,
        "frame_count": len(intervals),
        "mean_interval_s": statistics.mean(intervals),
        "max_interval_s": max(intervals),
        "dropped_count": len(dropped),
    }


def _check_marker_semantics(
    *,
    task_name: str,
    metadata: dict[str, Any],
    event_rows: list[dict[str, Any]],
    trial_rows: list[dict[str, Any]],
    events_by_trial: dict[int, list[dict[str, Any]]],
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    lsl_enabled = bool(metadata["marker_status"].get("lsl_enabled"))
    lpt_enabled = bool(metadata["marker_status"].get("lpt_enabled"))
    fnirs_enabled = bool(metadata["marker_status"].get("fnirs_enabled"))

    lsl_event_consistency = validate_event_trial_consistency(event_rows, trial_rows)
    if lsl_event_consistency:
        issues.append({"issue": "lsl_event_trial_consistency", "errors": lsl_event_consistency})

    for row in trial_rows:
        trial_index = int(row["trial_index"])
        trial_event_rows = events_by_trial.get(trial_index, [])
        event_rows_by_key = {str(event_row["event_key"]): event_row for event_row in trial_event_rows}
        ordered_rows: list[dict[str, Any]] = []
        missing_event_keys: list[str] = []
        for event_key in row.get("event_keys") or []:
            event_row = event_rows_by_key.get(str(event_key))
            if event_row is None:
                missing_event_keys.append(str(event_key))
                continue
            ordered_rows.append(event_row)
        if missing_event_keys:
            issues.append({"trial": trial_index, "issue": "missing_trial_event_keys", "event_keys": missing_event_keys})
            continue

        actual_lsl = [int(event_row["event_code"]) for event_row in ordered_rows if to_bool(event_row.get("lsl_sent")) is True]
        actual_lpt = [int(event_row["event_code"]) for event_row in ordered_rows if to_bool(event_row.get("lpt_sent")) is True]
        actual_fnirs = [
            _fnirs_code_for(task_name, metadata, int(event_row["event_code"]))
            for event_row in ordered_rows
            if to_bool(event_row.get("fnirs_sent")) is True
        ]

        if not lsl_enabled and row.get("lsl_marker_codes"):
            issues.append({"trial": trial_index, "issue": "lsl_disabled_but_trial_codes_present", "codes": row.get("lsl_marker_codes")})
        if not lpt_enabled and row.get("lpt_marker_codes"):
            issues.append({"trial": trial_index, "issue": "lpt_disabled_but_trial_codes_present", "codes": row.get("lpt_marker_codes")})
        if not fnirs_enabled and row.get("fnirs_marker_codes"):
            issues.append({"trial": trial_index, "issue": "fnirs_disabled_but_trial_codes_present", "codes": row.get("fnirs_marker_codes")})

        if list(row.get("lsl_marker_codes") or []) != actual_lsl:
            issues.append({"trial": trial_index, "issue": "lsl_marker_codes_mismatch", "observed": row.get("lsl_marker_codes"), "expected": actual_lsl})
        if list(row.get("lpt_marker_codes") or []) != actual_lpt:
            issues.append({"trial": trial_index, "issue": "lpt_marker_codes_mismatch", "observed": row.get("lpt_marker_codes"), "expected": actual_lpt})
        if list(row.get("fnirs_marker_codes") or []) != actual_fnirs:
            issues.append({"trial": trial_index, "issue": "fnirs_marker_codes_mismatch", "observed": row.get("fnirs_marker_codes"), "expected": actual_fnirs})

    return {
        "status": "fail" if issues else "pass",
        "issue_count": len(issues),
        "issues": issues[:20],
    }


def audit_run_directory(run_dir: Path | str) -> dict[str, Any]:
    resolved_run_dir = Path(run_dir)
    payload = load_run_payload(resolved_run_dir)
    metadata = payload["metadata"]
    event_rows = payload["event_rows"]
    trial_rows = expand_trial_rows(payload["trial_rows"])
    task_name = str(metadata["task"])
    events_by_trial = _build_event_rows_by_trial(event_rows)

    checks = {
        "event_completeness": _check_event_completeness(
            task_name=task_name,
            metadata=metadata,
            event_rows=event_rows,
            trial_rows=trial_rows,
            events_by_trial=events_by_trial,
        ),
        "event_clock_alignment": _check_event_clock_alignment(task_name=task_name, metadata=metadata, event_rows=event_rows),
        "phase_timing": _check_phase_timing(task_name=task_name, metadata=metadata, trial_rows=trial_rows),
        "frame_intervals": _check_frame_intervals(run_dir=resolved_run_dir, metadata=metadata),
        "marker_semantics": _check_marker_semantics(
            task_name=task_name,
            metadata=metadata,
            event_rows=event_rows,
            trial_rows=trial_rows,
            events_by_trial=events_by_trial,
        ),
    }

    errors = [f"{name}: {check['issue_count']} issue(s)" for name, check in checks.items() if check["status"] == "fail"]
    warnings = [f"{name}: {check['issue_count']} issue(s)" for name, check in checks.items() if check["status"] == "warning"]
    status = "fail" if errors else "warning" if warnings else "pass"

    return {
        "generated_at": iso_timestamp(),
        "run_dir": str(resolved_run_dir),
        "task": task_name,
        "practice_enabled": bool(metadata["config_snapshot"]["practice"]["enabled"]),
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "trial_count": len(trial_rows),
            "event_count": len(event_rows),
            "frame_rate_hz": _frame_rate_hz(metadata),
        },
        "checks": checks,
    }


def write_audit_report(path: Path | str, report: dict[str, Any]) -> Path:
    resolved_path = Path(path)
    resolved_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return resolved_path