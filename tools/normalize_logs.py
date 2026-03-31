from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from paradigm.runtime.logging_utils import INVALID_NUMERIC
from paradigm.runtime.utils import make_json_safe, to_json_string


EVENT_COMPLEX_FIELDS = {"extra_metadata"}
TRIAL_COMPLEX_FIELDS = {
    "stimulus_parameters",
    "lsl_marker_codes",
    "lpt_marker_codes",
    "event_keys",
    "fnirs_marker_codes",
    "task_specific_data",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="规范化现有 PsychoParadigm 运行日志的可读性")
    parser.add_argument("path", help="单个 run 目录，或上层 session 目录")
    parser.add_argument("--remove-psychopy-log", action="store_true", help="若存在 psychopy.log，则一并删除")
    return parser.parse_args()


def _discover_run_dirs(root: Path) -> list[Path]:
    if (root / "run_metadata.json").exists() and (root / "event_log.csv").exists() and (root / "trial_summary.csv").exists():
        return [root]
    return sorted(
        path
        for path in root.rglob("run_metadata.json")
        if (path.parent / "event_log.csv").exists() and (path.parent / "trial_summary.csv").exists()
    )


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _normalize_json_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (dict, list, tuple)):
        return to_json_string(value)
    text = str(value).strip()
    if not text:
        return ""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text
    return to_json_string(parsed)


def normalize_event_log(path: Path) -> None:
    fieldnames, rows = _read_csv(path)
    normalized_fieldnames = [field for field in fieldnames if field != "description"]
    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        normalized = {field: row.get(field, "") for field in normalized_fieldnames}
        if normalized.get("flip_time", "") in {"", None}:
            normalized["flip_time"] = INVALID_NUMERIC
        for field in EVENT_COMPLEX_FIELDS:
            if field in normalized:
                normalized[field] = _normalize_json_text(normalized[field])
        normalized_rows.append(normalized)
    _write_csv(path, normalized_fieldnames, normalized_rows)


def normalize_trial_summary(path: Path) -> None:
    fieldnames, rows = _read_csv(path)
    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        normalized = dict(row)
        for field in TRIAL_COMPLEX_FIELDS:
            if field in normalized:
                normalized[field] = _normalize_json_text(normalized[field])
        normalized_rows.append(normalized)
    _write_csv(path, fieldnames, normalized_rows)


def normalize_metadata(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps(make_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_run_dir(run_dir: Path, *, remove_psychopy_log: bool) -> None:
    normalize_event_log(run_dir / "event_log.csv")
    normalize_trial_summary(run_dir / "trial_summary.csv")
    normalize_metadata(run_dir / "run_metadata.json")
    if remove_psychopy_log:
        psychopy_log_path = run_dir / "psychopy.log"
        if psychopy_log_path.exists():
            psychopy_log_path.unlink()


def main() -> None:
    args = parse_args()
    root = Path(args.path)
    run_dirs = _discover_run_dirs(root)
    if not run_dirs:
        raise SystemExit("没有发现可规范化的 run 目录。")
    actual_run_dirs = [path.parent if path.name == "run_metadata.json" else path for path in run_dirs]
    for run_dir in actual_run_dirs:
        normalize_run_dir(run_dir, remove_psychopy_log=args.remove_psychopy_log)
        print(f"已规范化: {run_dir}")


if __name__ == "__main__":
    main()