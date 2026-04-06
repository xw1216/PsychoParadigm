from __future__ import annotations

from typing import Any


def summarize_prl_run(trial_rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_trials = len(trial_rows)
    non_timeout_rows = [row for row in trial_rows if not row.get("timeout")]
    optimal_rows = [row for row in non_timeout_rows if row.get("optimal_choice") is not None]
    switch_rows = [row for row in non_timeout_rows if row.get("switch_from_previous") is not None]
    win_stay_candidates = [row for row in non_timeout_rows if row.get("previous_feedback") == "reward"]
    lose_shift_candidates = [row for row in non_timeout_rows if row.get("previous_feedback") == "no_reward"]
    veridical_win_stay_candidates = [row for row in win_stay_candidates if not row.get("misleading_feedback")]
    misleading_no_reward_candidates = [row for row in lose_shift_candidates if row.get("misleading_feedback")]
    criterion_trials = [row.get("trials_to_criterion") for row in non_timeout_rows if row.get("criterion_reached") and row.get("trials_to_criterion") is not None]
    perseverative_rows = [row for row in non_timeout_rows if row.get("trial_phase") == "early_post_reversal"]
    regressive_rows = [row for row in non_timeout_rows if row.get("trial_phase") == "stable"]

    reversal_curve: dict[str, dict[str, float | int | None]] = {}
    for row in non_timeout_rows:
        offset = row.get("reversal_trial_offset")
        if offset is None:
            continue
        bucket = reversal_curve.setdefault(str(offset), {"n_trials": 0, "optimal_choice_rate": 0.0})
        bucket["n_trials"] = int(bucket["n_trials"]) + 1
        bucket["optimal_choice_rate"] = float(bucket["optimal_choice_rate"]) + (1.0 if row.get("optimal_choice") else 0.0)

    for bucket in reversal_curve.values():
        if bucket["n_trials"]:
            bucket["optimal_choice_rate"] = float(bucket["optimal_choice_rate"]) / int(bucket["n_trials"])

    return {
        "n_trials": total_trials,
        "timeout_rate": (sum(1 for row in trial_rows if row.get("timeout")) / total_trials) if total_trials else None,
        "optimal_choice_rate": (sum(1 for row in optimal_rows if row.get("optimal_choice")) / len(optimal_rows)) if optimal_rows else None,
        "mean_rt": (sum(row["rt"] for row in non_timeout_rows if row.get("rt") is not None) / count) if (count := sum(1 for row in non_timeout_rows if row.get("rt") is not None)) else None,
        "win_stay_rate": (sum(1 for row in win_stay_candidates if not row.get("switch_from_previous")) / len(win_stay_candidates)) if win_stay_candidates else None,
        "lose_shift_rate": (sum(1 for row in lose_shift_candidates if row.get("switch_from_previous")) / len(lose_shift_candidates)) if lose_shift_candidates else None,
        "veridical_win_stay_rate": (sum(1 for row in veridical_win_stay_candidates if not row.get("switch_from_previous")) / len(veridical_win_stay_candidates)) if veridical_win_stay_candidates else None,
        "misleading_lose_shift_rate": (sum(1 for row in misleading_no_reward_candidates if row.get("switch_from_previous")) / len(misleading_no_reward_candidates)) if misleading_no_reward_candidates else None,
        "switch_rate": (sum(1 for row in switch_rows if row.get("switch_from_previous")) / len(switch_rows)) if switch_rows else None,
        "mean_trials_to_criterion": (sum(criterion_trials) / len(criterion_trials)) if criterion_trials else None,
        "perseverative_error_rate": (sum(1 for row in perseverative_rows if row.get("optimal_choice") is False) / len(perseverative_rows)) if perseverative_rows else None,
        "regressive_error_rate": (sum(1 for row in regressive_rows if row.get("optimal_choice") is False) / len(regressive_rows)) if regressive_rows else None,
        "reversal_curve": reversal_curve,
    }