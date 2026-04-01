import argparse
from pathlib import Path

from paradigm.data.bids import build_bids_beh_rows, build_bids_event_rows, export_run_to_bids


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