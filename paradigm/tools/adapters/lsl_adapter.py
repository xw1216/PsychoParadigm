from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import BaseStreamAdapter
from ..stream_types import MarkerEvent, StreamDescriptor, UnifiedStreamData, infer_stream_kind, marker_value_from_raw


def _stream_info_value(stream_info: Any, attr_name: str) -> Any:
    value = getattr(stream_info, attr_name, None)
    if callable(value):
        try:
            return value()
        except TypeError:
            return value
    return value


@dataclass(slots=True)
class LSLMarkerSubscription:
    descriptor: StreamDescriptor
    inlet: Any
    time_zero: float | None = None
    total_events: int = 0
    recent_events: list[MarkerEvent] = field(default_factory=list)

    def pull(self, *, max_samples: int = 256, timeout: float = 0.0) -> list[MarkerEvent]:
        events: list[MarkerEvent] = []
        for _ in range(max_samples):
            sample, timestamp = self.inlet.pull_sample(timeout=timeout)
            if sample is None:
                break
            raw_value = sample[0] if sample else ""
            marker_value, label, metadata = marker_value_from_raw(raw_value)
            if self.time_zero is None:
                self.time_zero = float(timestamp)
            self.total_events += 1
            event = MarkerEvent(
                index=self.total_events,
                time_s=float(timestamp) - self.time_zero,
                value=marker_value,
                raw_value=str(raw_value),
                label=label,
                metadata=metadata,
            )
            events.append(event)
        if events:
            self.recent_events.extend(events)
        return events


class LSLStreamAdapter(BaseStreamAdapter):
    def __init__(self, *, pylsl_module: Any | None = None, resolve_timeout: float = 3.0) -> None:
        self.resolve_timeout = resolve_timeout
        if pylsl_module is None:
            try:
                import pylsl
            except ImportError as exc:  # pragma: no cover
                missing = exc.name or "pylsl"
                raise RuntimeError(f"缺少依赖：{missing}") from exc
            pylsl_module = pylsl
        self.pylsl = pylsl_module

    def _discover_stream_infos(self) -> list[Any]:
        if hasattr(self.pylsl, "resolve_streams"):
            try:
                return list(self.pylsl.resolve_streams(wait_time=self.resolve_timeout))
            except TypeError:
                return list(self.pylsl.resolve_streams(self.resolve_timeout))
        return []

    def list_streams(self) -> list[StreamDescriptor]:
        descriptors: list[StreamDescriptor] = []
        for index, stream_info in enumerate(self._discover_stream_infos()):
            stream_type = str(_stream_info_value(stream_info, "type") or "")
            descriptors.append(
                StreamDescriptor(
                    stream_id=f"lsl:{index}",
                    name=str(_stream_info_value(stream_info, "name") or f"stream_{index}"),
                    kind=infer_stream_kind(stream_type),
                    source_id=str(_stream_info_value(stream_info, "source_id") or "") or None,
                    stream_type=stream_type,
                    nominal_srate=float(_stream_info_value(stream_info, "nominal_srate") or 0.0),
                    channel_count=int(_stream_info_value(stream_info, "channel_count") or 0),
                    origin="lsl",
                    metadata={"stream_info": stream_info},
                )
            )
        return descriptors

    def load_marker_stream(self, stream_id: str) -> UnifiedStreamData:
        descriptor = self._descriptor_by_id(stream_id)
        subscription = self.open_marker_subscription(stream_id)
        events = subscription.pull(max_samples=4096, timeout=0.0)
        return UnifiedStreamData(descriptor=descriptor, marker_events=events)

    def open_marker_subscription(self, stream_id: str) -> LSLMarkerSubscription:
        descriptor = self._descriptor_by_id(stream_id)
        if descriptor.kind.value != "marker":
            raise ValueError(f"当前只支持 marker stream，收到的是 {descriptor.kind.value}")
        stream_info = descriptor.metadata.get("stream_info")
        inlet = self.pylsl.StreamInlet(stream_info, recover=True)
        return LSLMarkerSubscription(descriptor=descriptor, inlet=inlet)

    def _descriptor_by_id(self, stream_id: str) -> StreamDescriptor:
        for descriptor in self.list_streams():
            if descriptor.stream_id == stream_id:
                return descriptor
        raise KeyError(f"未找到 stream_id={stream_id}")
