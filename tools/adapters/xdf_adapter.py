from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from tools.adapters.base import BaseStreamAdapter
from tools.stream_types import MarkerEvent, StreamDescriptor, UnifiedStreamData, infer_stream_kind, marker_value_from_raw


def _xdf_info_value(stream: dict[str, Any], key: str, default: Any = None) -> Any:
    value = stream.get("info", {}).get(key, default)
    if isinstance(value, list):
        return value[0] if value else default
    return value


def _relative_times(time_stamps: list[Any]) -> list[float]:
    if not time_stamps:
        return []
    base = float(time_stamps[0])
    return [float(item) - base for item in time_stamps]


class XDFStreamAdapter(BaseStreamAdapter):
    def __init__(
        self,
        xdf_path: str | Path,
        *,
        loader: Callable[[str], tuple[list[dict[str, Any]], dict[str, Any]]] | None = None,
    ) -> None:
        self.xdf_path = Path(xdf_path)
        self._loader = loader
        self._streams: list[dict[str, Any]] | None = None
        self._header: dict[str, Any] | None = None

    def _ensure_loaded(self) -> None:
        if self._streams is not None and self._header is not None:
            return
        if self._loader is None:
            try:
                import pyxdf
            except ImportError as exc:  # pragma: no cover
                missing = exc.name or "pyxdf"
                raise RuntimeError(f"缺少依赖：{missing}") from exc
            self._loader = pyxdf.load_xdf
        self._streams, self._header = self._loader(str(self.xdf_path))

    def list_streams(self) -> list[StreamDescriptor]:
        self._ensure_loaded()
        assert self._streams is not None
        descriptors: list[StreamDescriptor] = []
        for index, stream in enumerate(self._streams):
            stream_type = str(_xdf_info_value(stream, "type", "") or "")
            descriptors.append(
                StreamDescriptor(
                    stream_id=f"xdf:{index}",
                    name=str(_xdf_info_value(stream, "name", f"stream_{index}")),
                    kind=infer_stream_kind(stream_type),
                    source_id=str(_xdf_info_value(stream, "source_id", "") or "") or None,
                    stream_type=stream_type,
                    nominal_srate=float(_xdf_info_value(stream, "nominal_srate", 0.0) or 0.0),
                    channel_count=int(_xdf_info_value(stream, "channel_count", 0) or 0),
                    sample_count=len(stream.get("time_stamps", [])),
                    origin=self.xdf_path,
                )
            )
        return descriptors

    def load_marker_stream(self, stream_id: str) -> UnifiedStreamData:
        self._ensure_loaded()
        assert self._streams is not None
        index = int(stream_id.split(":", 1)[1])
        stream = self._streams[index]
        descriptor = self.list_streams()[index]
        if descriptor.kind.value != "marker":
            raise ValueError(f"当前只支持 marker stream，收到的是 {descriptor.kind.value}")

        events: list[MarkerEvent] = []
        time_stamps = _relative_times(stream.get("time_stamps", []))
        for event_index, (time_s, raw_entry) in enumerate(zip(time_stamps, stream.get("time_series", [])), start=1):
            raw_value = raw_entry[0] if isinstance(raw_entry, (list, tuple)) and raw_entry else raw_entry
            marker_value, label, metadata = marker_value_from_raw(raw_value)
            events.append(
                MarkerEvent(
                    index=event_index,
                    time_s=float(time_s),
                    value=marker_value,
                    raw_value=str(raw_value),
                    label=label,
                    metadata=metadata,
                )
            )
        return UnifiedStreamData(descriptor=descriptor, marker_events=events, metadata={"header": self._header or {}})
