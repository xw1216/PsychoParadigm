from __future__ import annotations

import argparse
from pathlib import Path

from paradigm.data.normalize import discover_run_dirs, normalize_run_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="规范化现有 PsychoParadigm 运行日志的可读性")
    parser.add_argument("path", help="单个 run 目录，或上层 session 目录")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.path)
    run_dirs = discover_run_dirs(root)
    if not run_dirs:
        raise SystemExit("没有发现可规范化的 run 目录。")
    actual_run_dirs = [path.parent if path.name == "run_metadata.json" else path for path in run_dirs]
    for run_dir in actual_run_dirs:
        normalize_run_dir(run_dir)
        print(f"已规范化: {run_dir}")


if __name__ == "__main__":
    main()