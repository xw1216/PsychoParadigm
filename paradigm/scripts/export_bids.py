import argparse
import csv
import json
from pathlib import Path
from typing import Any

from paradigm.runtime.schemas import get_task_specific_data_fields


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_or_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return "n/a"
    if stripped in {"None", "null"}:
        return "n/a"
    if stripped[0] in "[{":
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return value
    return value


def _normalize_scalar(value: Any) -> Any:
    parsed = _json_or_value(value)
    if parsed is None:
        return "n/a"
    if isinstance(parsed, bool):
        return "true" if parsed else "false"
    if isinstance(parsed, (dict, list)):
        return json.dumps(parsed, ensure_ascii=True, sort_keys=True)
    return parsed


def _trial_lookup(trial_rows: list[dict[str, str]]) -> dict[tuple[str, int], dict[str, Any]]:
    lookup: dict[tuple[str, int], dict[str, Any]] = {}
    for row in trial_rows:
        task = row.get("task")
        trial_index = row.get("trial_index")
        if task in {None, ""} or trial_index in {None, ""}:
            continue
        lookup[(str(task), int(trial_index))] = row
    return lookup


def build_bids_event_rows(event_rows: list[dict[str, str]], trial_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    trials = _trial_lookup(trial_rows)
    bids_rows: list[dict[str, Any]] = []
    for event_row in event_rows:
        task = event_row.get("task")
        trial_value = event_row.get("trial")
        trial_row = None
        if task not in {None, ""} and trial_value not in {None, ""}:
            trial_row = trials.get((str(task), int(trial_value)))
        feedback_value = trial_row.get("feedback") if trial_row else "n/a"
        bids_rows.append(
            {
                "onset": float(event_row["task_time"]) if event_row.get("task_time") not in {None, ""} else 0.0,
                "duration": 0.0,
                "event_key": event_row.get("event_key") or "n/a",
                "event_code": int(event_row["event_code"]) if event_row.get("event_code") not in {None, "", "None"} else "n/a",
                "block": int(event_row["block"]) if event_row.get("block") not in {None, "", "None"} else "n/a",
                "trial": int(event_row["trial"]) if event_row.get("trial") not in {None, "", "None"} else "n/a",
                "response_time": float(trial_row["rt"]) if trial_row and trial_row.get("rt") not in {None, "", "None"} else "n/a",
                "response": trial_row.get("response", "n/a") if trial_row else "n/a",
                "feedback": feedback_value if feedback_value not in {None, "", "None"} else "n/a",
                "accuracy": _normalize_scalar(trial_row.get("correct")) if trial_row else "n/a",
                "timeout": _normalize_scalar(trial_row.get("timeout")) if trial_row else "n/a",
            }
        )
    return bids_rows


def build_bids_beh_rows(trial_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    bids_rows: list[dict[str, Any]] = []
    for row in trial_rows:
        bids_rows.append(
            {
                "onset": float(row["stim_onset"]) if row.get("stim_onset") not in {None, "", "None"} else "n/a",
                "duration": (float(row["trial_end"]) - float(row["stim_onset"])) if row.get("trial_end") not in {None, "", "None"} and row.get("stim_onset") not in {None, "", "None"} else "n/a",
                "condition": _normalize_scalar(row.get("condition")),
                "block": _normalize_scalar(row.get("block")),
                "trial_index": _normalize_scalar(row.get("trial_index")),
                "response_time": _normalize_scalar(row.get("rt")),
                "response": _normalize_scalar(row.get("response")),
                "accuracy": _normalize_scalar(row.get("correct")),
                "feedback": _normalize_scalar(row.get("feedback")),
                "timeout": _normalize_scalar(row.get("timeout")),
                "stimulus_parameters": _normalize_scalar(row.get("stimulus_parameters")),
                "event_keys": _normalize_scalar(row.get("event_keys")),
                "event_codes": _normalize_scalar(row.get("lsl_marker_codes")),
                "fnirs_marker_codes": _normalize_scalar(row.get("fnirs_marker_codes")),
                "task_specific_data": _normalize_scalar(row.get("task_specific_data")),
            }
        )
    return bids_rows


def _write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _normalize_scalar(value) for key, value in row.items()})


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _append_participant(participants_path: Path, participant: str) -> None:
    participants_path.parent.mkdir(parents=True, exist_ok=True)
    existing = set()
    if participants_path.exists():
        with participants_path.open("r", encoding="utf-8") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                existing.add(row.get("participant_id"))
    if participant in existing:
        return
    write_header = not participants_path.exists()
    with participants_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["participant_id"], delimiter="\t")
        if write_header:
            writer.writeheader()
        writer.writerow({"participant_id": participant})


def export_run_to_bids(run_dir: Path, bids_root: Path) -> dict[str, Path]:
    metadata = _read_json(run_dir / "run_metadata.json")
    participant = f"sub-{metadata['participant']}"
    session = f"ses-{metadata['session']}"
    task = metadata["task"]
    acq = run_dir.name.replace("_", "")

    event_rows = _read_csv_rows(run_dir / "event_log.csv")
    trial_rows = _read_csv_rows(run_dir / "trial_summary.csv")
    events_tsv_rows = build_bids_event_rows(event_rows, trial_rows)
    beh_tsv_rows = build_bids_beh_rows(trial_rows)

    beh_dir = bids_root / participant / session / "beh"
    base_name = f"{participant}_{session}_task-{task}_acq-{acq}"
    events_tsv_path = beh_dir / f"{base_name}_events.tsv"
    events_json_path = beh_dir / f"{base_name}_events.json"
    beh_tsv_path = beh_dir / f"{base_name}_beh.tsv"
    beh_json_path = beh_dir / f"{base_name}_beh.json"

    _write_tsv(events_tsv_path, events_tsv_rows)
    _write_tsv(beh_tsv_path, beh_tsv_rows)
    _write_json(
        events_json_path,
        {
            "onset": {"Description": "Seconds from task start."},
            "duration": {"Description": "Event duration in seconds. Instantaneous markers are stored as 0."},
            "event_key": {
                "Description": "Semantic runtime event key emitted by the task.",
                "Levels": metadata.get("event_codebook", {}).get(task, {}),
            },
            "event_code": {"Description": "Single-byte hardware marker code used for runtime transport/logging over LSL/LPT; semantic meaning remains defined by event_key."},
            "response_time": {"Description": "Behavioral response time in seconds when available."},
        },
    )
    _write_json(
        beh_json_path,
        {
            "onset": {"Description": "Stimulus onset in seconds from task start."},
            "duration": {"Description": "Approximate trial duration from stimulus onset to trial end."},
            "condition": {"Description": "Task condition label used for downstream behavior analysis."},
            "stimulus_parameters": {"Description": "JSON-serialized stimulus configuration for the trial."},
            "event_keys": {"Description": "Summary-only ordered semantic event_key list for the trial; event_log.csv remains the ground-truth event source."},
            "event_codes": {"Description": "Summary-only ordered LSL event codes observed in the trial; event_log.csv remains the ground-truth event source."},
            "fnirs_marker_codes": {"Description": "Summary-only fNIRS namespace marker codes when namespace logging is enabled. This reflects a stable naming/logging layer, not a completed vendor-specific hardware adapter."},
            "task_specific_data": {
                "Description": "JSON-serialized task-specific or analysis-helper fields retained outside the shared trial_summary core columns.",
                "Fields": get_task_specific_data_fields(task),
            },
        },
    )
    dataset_description = bids_root / "dataset_description.json"
    if not dataset_description.exists():
        _write_json(dataset_description, {"Name": "PsychoParadigm", "BIDSVersion": "1.9.0", "DatasetType": "raw"})
    _append_participant(bids_root / "participants.tsv", participant)

    return {
        "events_tsv": events_tsv_path,
        "events_json": events_json_path,
        "beh_tsv": beh_tsv_path,
        "beh_json": beh_json_path,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert a PsychoParadigm run directory to BIDS-ready behavior and event files")
    parser.add_argument("run_dir", help="Path to a single run directory containing run_metadata.json, event_log.csv and trial_summary.csv")
    parser.add_argument("--bids-root", required=True, help="Target root directory for BIDS-ready behavior and event outputs")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    export_run_to_bids(Path(args.run_dir), Path(args.bids_root))


if __name__ == "__main__":
    main()