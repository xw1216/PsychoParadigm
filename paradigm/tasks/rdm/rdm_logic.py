import csv
import random
from dataclasses import dataclass
from pathlib import Path

from paradigm.config import RDMTaskConfig


@dataclass(slots=True)
class RDMTrial:
    block: int
    trial_index: int
    direction: str
    coherence: float


def resolve_rdm_feedback_plan(*, correct: bool, timeout: bool, feedback_mode: str) -> tuple[str | None, str | None, str | None]:
    if feedback_mode == "none":
        return "omitted", None, None
    if timeout:
        return "timeout", "feedback.timeout", "反应过慢"
    if correct:
        return "correct", "feedback.correct", "正确"
    return "incorrect", "feedback.incorrect", "错误"


def determine_rdm_trial_quality(*, timeout: bool, fixation_break_detected: bool, invalid_response: bool, exclude_timeouts_from_analysis: bool) -> tuple[bool, str | None]:
    if fixation_break_detected:
        return True, "fixation_break"
    if invalid_response:
        return True, "invalid_response"
    if timeout and exclude_timeouts_from_analysis:
        return True, "timeout"
    return False, None


def build_rdm_trials(task_config: RDMTaskConfig, rng: random.Random) -> list[RDMTrial]:
    condition_grid: list[tuple[str, float]] = []
    for direction in task_config.directions:
        for coherence in task_config.coherence_levels:
            for _ in range(task_config.trials_per_condition):
                condition_grid.append((direction, coherence))
    rng.shuffle(condition_grid)

    total_trials = len(condition_grid)
    block_size = max(1, total_trials // task_config.blocks)
    trials: list[RDMTrial] = []
    for index, (direction, coherence) in enumerate(condition_grid, start=1):
        block = min(((index - 1) // block_size) + 1, task_config.blocks)
        trials.append(RDMTrial(block=block, trial_index=index, direction=direction, coherence=coherence))
    return trials


def export_psychometric_summary(trial_rows: list[dict], output_path: Path) -> None:
    grouped: dict[float, dict[str, float]] = {}
    for row in trial_rows:
        if row.get("exclude_trial"):
            continue
        coherence = float(row["coherence"])
        bucket = grouped.setdefault(coherence, {"count": 0.0, "accuracy_sum": 0.0, "rt_sum": 0.0, "rt_count": 0.0})
        bucket["count"] += 1.0
        bucket["accuracy_sum"] += 1.0 if row.get("correct") else 0.0
        if row.get("rt") is not None:
            bucket["rt_sum"] += float(row["rt"])
            bucket["rt_count"] += 1.0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["coherence", "n_trials", "accuracy", "mean_rt"])
        writer.writeheader()
        for coherence in sorted(grouped):
            bucket = grouped[coherence]
            writer.writerow(
                {
                    "coherence": coherence,
                    "n_trials": int(bucket["count"]),
                    "accuracy": bucket["accuracy_sum"] / bucket["count"],
                    "mean_rt": (bucket["rt_sum"] / bucket["rt_count"]) if bucket["rt_count"] else "",
                }
            )


def export_ddm_ready_table(trial_rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["trial_index", "coherence", "direction", "response", "correct", "rt", "timeout", "response_locked_rt", "cpp_slope_proxy", "exclude_trial", "exclude_reason"])
        writer.writeheader()
        for row in trial_rows:
            writer.writerow(
                {
                    "trial_index": row.get("trial_index"),
                    "coherence": row.get("coherence"),
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
