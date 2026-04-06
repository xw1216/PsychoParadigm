from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def export_psychometric_summary(trial_rows: list[dict[str, Any]], output_path: Path) -> None:
    grouped: dict[float, dict[str, float]] = {}
    for row in trial_rows:
        if row.get("exclude_trial") or row.get("signed_coherence") is None:
            continue
        signed_coherence = float(row["signed_coherence"])
        bucket = grouped.setdefault(
            signed_coherence,
            {"count": 0.0, "right_choices": 0.0, "accuracy_sum": 0.0, "rt_sum": 0.0, "rt_count": 0.0},
        )
        bucket["count"] += 1.0
        bucket["right_choices"] += 1.0 if row.get("response") == "right" else 0.0
        bucket["accuracy_sum"] += 1.0 if row.get("correct") else 0.0
        if row.get("rt") is not None:
            bucket["rt_sum"] += float(row["rt"])
            bucket["rt_count"] += 1.0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["signed_coherence", "absolute_coherence", "n_trials", "p_right", "accuracy", "mean_rt"])
        writer.writeheader()
        for signed_coherence in sorted(grouped):
            bucket = grouped[signed_coherence]
            writer.writerow(
                {
                    "signed_coherence": signed_coherence,
                    "absolute_coherence": abs(signed_coherence),
                    "n_trials": int(bucket["count"]),
                    "p_right": bucket["right_choices"] / bucket["count"],
                    "accuracy": bucket["accuracy_sum"] / bucket["count"],
                    "mean_rt": (bucket["rt_sum"] / bucket["rt_count"]) if bucket["rt_count"] else "",
                }
            )


def export_chronometric_summary(trial_rows: list[dict[str, Any]], output_path: Path) -> None:
    grouped: dict[tuple[float, str], dict[str, float]] = {}
    for row in trial_rows:
        if row.get("exclude_trial") or row.get("absolute_coherence") is None or row.get("rt") is None:
            continue
        key = (float(row["absolute_coherence"]), "correct" if row.get("correct") else "error")
        bucket = grouped.setdefault(key, {"count": 0.0, "rt_sum": 0.0})
        bucket["count"] += 1.0
        bucket["rt_sum"] += float(row["rt"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["absolute_coherence", "outcome", "n_trials", "mean_rt"])
        writer.writeheader()
        for (absolute_coherence, outcome) in sorted(grouped):
            bucket = grouped[(absolute_coherence, outcome)]
            writer.writerow(
                {
                    "absolute_coherence": absolute_coherence,
                    "outcome": outcome,
                    "n_trials": int(bucket["count"]),
                    "mean_rt": bucket["rt_sum"] / bucket["count"],
                }
            )


def export_ddm_ready_table(trial_rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "trial_index",
                "signed_coherence",
                "absolute_coherence",
                "direction",
                "response",
                "correct",
                "rt",
                "timeout",
                "response_locked_rt",
                "cpp_slope_proxy",
                "exclude_trial",
                "exclude_reason",
            ],
        )
        writer.writeheader()
        for row in trial_rows:
            writer.writerow(
                {
                    "trial_index": row.get("trial_index"),
                    "signed_coherence": row.get("signed_coherence"),
                    "absolute_coherence": row.get("absolute_coherence"),
                    "direction": row.get("direction"),
                    "response": row.get("response"),
                    "correct": row.get("correct"),
                    "rt": row.get("rt"),
                    "timeout": row.get("timeout"),
                    "response_locked_rt": row.get("response_locked_rt"),
                    "cpp_slope_proxy": row.get("cpp_slope_proxy"),
                    "exclude_trial": row.get("exclude_trial"),
                    "exclude_reason": row.get("exclude_reason"),
                }
            )