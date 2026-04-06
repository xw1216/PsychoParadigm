from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from paradigm.analysis import summarize_doors_run, summarize_prl_run, summarize_rdm_run
from paradigm.data.run_io import expand_trial_rows, load_run_payload


ANALYZERS = {
    "doors": (summarize_doors_run, "doors_behavior_summary.json"),
    "prl": (summarize_prl_run, "prl_behavior_summary.json"),
    "rdm": (summarize_rdm_run, "rdm_behavior_summary.json"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export task-specific behavioral summary metrics from a PsychoParadigm run directory")
    parser.add_argument("run_dir", help="Path to a single run directory containing run_metadata.json, event_log.csv and trial_summary.csv")
    parser.add_argument("--output", default=None, help="Optional output file path; defaults to a task-specific JSON file in the run directory")
    return parser.parse_args()


def _write_flat_csv(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric", "value"])
        writer.writeheader()
        for key, value in payload.items():
            writer.writerow({"metric": key, "value": json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value})


def main() -> None:
    args = parse_args()
    run_dir = Path(args.run_dir)
    payload = load_run_payload(run_dir)
    task_name = str(payload["metadata"]["task"])
    analyzer, default_name = ANALYZERS[task_name]
    trial_rows = expand_trial_rows(payload["trial_rows"])
    summary = analyzer(trial_rows)
    output_path = Path(args.output) if args.output else run_dir / default_name
    output_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_flat_csv(output_path.with_suffix(".csv"), summary)


if __name__ == "__main__":
    main()