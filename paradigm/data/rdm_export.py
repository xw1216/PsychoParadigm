from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from paradigm.analysis.rdm import export_chronometric_summary, export_ddm_ready_table, export_psychometric_summary
from paradigm.data.run_io import parse_json_field, to_bool, to_float, to_int


def _read_trial_rows(trial_summary_path: Path) -> list[dict[str, str]]:
    with trial_summary_path.open("r", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_normalized_rdm_rows(trial_summary_path: Path) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in _read_trial_rows(trial_summary_path):
        task_specific_payload = parse_json_field(row.get("task_specific_data"), default={})
        exclude_trial_value = task_specific_payload.get("exclude_trial")
        normalized.append(
            {
                "trial_index": to_int(row.get("trial_index")),
                "signed_coherence": to_float(task_specific_payload.get("signed_coherence")),
                "absolute_coherence": to_float(task_specific_payload.get("absolute_coherence") or task_specific_payload.get("coherence")),
                "direction": task_specific_payload.get("direction"),
                "response": row.get("response"),
                "correct": to_bool(row.get("correct")) is True,
                "rt": to_float(row.get("rt")),
                "timeout": to_bool(row.get("timeout")) is True,
                "response_locked_rt": to_float(task_specific_payload.get("response_locked_rt")),
                "cpp_slope_proxy": to_float(task_specific_payload.get("cpp_slope_proxy")),
                "exclude_trial": to_bool(exclude_trial_value),
                "exclude_reason": task_specific_payload.get("exclude_reason"),
            }
        )
    return normalized


__all__ = [
    "export_chronometric_summary",
    "export_ddm_ready_table",
    "export_psychometric_summary",
    "load_normalized_rdm_rows",
]