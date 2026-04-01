from __future__ import annotations

import argparse
from pathlib import Path

from ..adapters import XDFStreamAdapter
from .matplotlib_views import MarkerTimelineViewer
from ..stream_types import (
    StreamDescriptor,
    StreamKind,
    print_stream_summary,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="轻量 XDF viewer，当前优先支持 marker 流")
    parser.add_argument("xdf_path", help=".xdf 文件路径")
    parser.add_argument("--stream-name", default=None, help="按 stream name 选择 marker 流")
    parser.add_argument("--stream-index", type=int, default=None, help="按列表中的 1-based 序号选择 marker 流")
    parser.add_argument("--list-only", action="store_true", help="只列出 streams，不打开图形")
    parser.add_argument("--export-path", default=None, help="按 e 导出当前可见 marker 表时使用的输出路径")
    return parser.parse_args()


def choose_marker_stream(descriptors: list[StreamDescriptor], *, stream_name: str | None, stream_index: int | None) -> StreamDescriptor:
    marker_streams = [descriptor for descriptor in descriptors if descriptor.kind == StreamKind.MARKER]
    if not marker_streams:
        raise SystemExit("XDF 中没有 marker 流。")
    if stream_name is not None:
        for descriptor in marker_streams:
            if descriptor.name == stream_name:
                return descriptor
        raise SystemExit(f"未找到名为 {stream_name!r} 的 marker 流。")
    if stream_index is not None:
        if 1 <= stream_index <= len(marker_streams):
            return marker_streams[stream_index - 1]
        raise SystemExit(f"marker stream 序号越界：{stream_index}")
    if len(marker_streams) == 1:
        return marker_streams[0]

    print("\n检测到多个 marker 流，请选择要查看的流：")
    for index, descriptor in enumerate(marker_streams, start=1):
        print(f"  [{index}] {descriptor.name} (source_id={descriptor.source_id or '-'})")
    typed = input("输入序号并回车: ").strip()
    try:
        selection = int(typed)
    except ValueError as exc:
        raise SystemExit("输入的不是有效整数序号。") from exc
    if 1 <= selection <= len(marker_streams):
        return marker_streams[selection - 1]
    raise SystemExit(f"marker stream 序号越界：{selection}")


def main() -> None:
    args = parse_args()
    adapter = XDFStreamAdapter(Path(args.xdf_path))
    descriptors = adapter.list_streams()
    print_stream_summary(descriptors)
    if args.list_only:
        return
    descriptor = choose_marker_stream(descriptors, stream_name=args.stream_name, stream_index=args.stream_index)
    stream_data = adapter.load_marker_stream(descriptor.stream_id)
    MarkerTimelineViewer(stream_data, export_path=args.export_path).show()


if __name__ == "__main__":
    main()
