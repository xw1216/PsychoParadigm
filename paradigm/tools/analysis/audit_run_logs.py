from __future__ import annotations

import argparse
from pathlib import Path

from paradigm.analysis.log_audit import AUDIT_REPORT_NAME, audit_run_directory, write_audit_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit a PsychoParadigm run directory for event completeness, timing, dropped frames, and marker semantics")
    parser.add_argument("run_dir", help="Path to a single run directory containing run_metadata.json, event_log.csv, trial_summary.csv, and frame_intervals.csv")
    parser.add_argument("--output", default=None, help="Optional output JSON path; defaults to log_audit.json in the run directory")
    parser.add_argument("--strict", action="store_true", help="Exit with code 1 when the audit status is fail")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = Path(args.run_dir)
    report = audit_run_directory(run_dir)
    output_path = Path(args.output) if args.output else run_dir / AUDIT_REPORT_NAME
    write_audit_report(output_path, report)
    print(f"[{report['status']}] log audit written to {output_path}")
    if args.strict and report["status"] == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()