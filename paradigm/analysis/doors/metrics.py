from __future__ import annotations

from collections import Counter
from statistics import median
from typing import Any


def summarize_doors_run(trial_rows: list[dict[str, Any]], *, fast_rt_threshold_s: float = 0.15) -> dict[str, Any]:
    total_trials = len(trial_rows)
    timeout_trials = [row for row in trial_rows if row.get("timeout")]
    valid_rows = [row for row in trial_rows if not row.get("timeout") and row.get("rt") is not None]
    feedback_counts = Counter(str(row.get("feedback")) for row in trial_rows)
    response_counts = Counter(str(row.get("response")) for row in trial_rows if row.get("response"))
    block_feedback_balance: dict[str, dict[str, int]] = {}
    for row in trial_rows:
        block = row.get("block")
        if block is None:
            continue
        balance = block_feedback_balance.setdefault(str(block), {"gain": 0, "loss": 0, "timeout": 0})
        feedback = str(row.get("feedback"))
        if feedback in balance:
            balance[feedback] += 1

    return {
        "n_trials": total_trials,
        "timeout_rate": (len(timeout_trials) / total_trials) if total_trials else None,
        "fast_rt_rate": (sum(1 for row in valid_rows if (row.get("rt") or 0.0) < fast_rt_threshold_s) / len(valid_rows)) if valid_rows else None,
        "left_choice_rate": (response_counts.get("left", 0) / sum(response_counts.values())) if response_counts else None,
        "mean_rt": (sum(row["rt"] for row in valid_rows) / len(valid_rows)) if valid_rows else None,
        "median_rt": median([row["rt"] for row in valid_rows]) if valid_rows else None,
        "feedback_counts": dict(feedback_counts),
        "block_feedback_balance": block_feedback_balance,
        "block_mean_rt": {
            str(block): (sum(row["rt"] for row in valid_rows if row.get("block") == block) / count)
            for block in sorted({row.get("block") for row in valid_rows if row.get("block") is not None})
            if (count := sum(1 for row in valid_rows if row.get("block") == block))
        },
    }