from __future__ import annotations

from typing import Any


def summarize_rdm_run(trial_rows: list[dict[str, Any]], *, fast_rt_threshold_s: float = 0.15) -> dict[str, Any]:
    total_trials = len(trial_rows)
    valid_rows = [row for row in trial_rows if not row.get("timeout") and row.get("rt") is not None]
    coherence_levels = sorted({row.get("signed_coherence") for row in trial_rows if row.get("signed_coherence") is not None})
    psychometric = {}
    chronometric = {}
    for level in coherence_levels:
        level_rows = [row for row in valid_rows if row.get("signed_coherence") == level]
        if not level_rows:
            continue
        psychometric[str(level)] = sum(1 for row in level_rows if row.get("response") == "right") / len(level_rows)
        chronometric[str(level)] = sum(row["rt"] for row in level_rows) / len(level_rows)

    abs_levels = sorted({abs(row.get("signed_coherence")) for row in valid_rows if row.get("signed_coherence") is not None})
    accuracy_by_abs = {}
    rt_by_abs = {}
    correct_rt_by_abs = {}
    error_rt_by_abs = {}
    for level in abs_levels:
        level_rows = [row for row in valid_rows if abs(row.get("signed_coherence")) == level]
        if not level_rows:
            continue
        accuracy_by_abs[str(level)] = sum(1 for row in level_rows if row.get("correct")) / len(level_rows)
        rt_by_abs[str(level)] = sum(row["rt"] for row in level_rows) / len(level_rows)
        correct_rows = [row for row in level_rows if row.get("correct")]
        error_rows = [row for row in level_rows if not row.get("correct")]
        correct_rt_by_abs[str(level)] = (sum(row["rt"] for row in correct_rows) / len(correct_rows)) if correct_rows else None
        error_rt_by_abs[str(level)] = (sum(row["rt"] for row in error_rows) / len(error_rows)) if error_rows else None

    return {
        "n_trials": total_trials,
        "timeout_rate": (sum(1 for row in trial_rows if row.get("timeout")) / total_trials) if total_trials else None,
        "fast_rt_rate": (sum(1 for row in valid_rows if (row.get("rt") or 0.0) < fast_rt_threshold_s) / len(valid_rows)) if valid_rows else None,
        "psychometric_right_choice": psychometric,
        "accuracy_by_abs_coherence": accuracy_by_abs,
        "mean_rt_by_abs_coherence": rt_by_abs,
        "correct_mean_rt_by_abs_coherence": correct_rt_by_abs,
        "error_mean_rt_by_abs_coherence": error_rt_by_abs,
        "chronometric_signed": chronometric,
    }