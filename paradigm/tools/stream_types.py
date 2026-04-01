from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class StreamKind(StrEnum):
    MARKER = "marker"
    EEG = "eeg"
    FNIRS = "fnirs"
    EYE_TRACKER = "eye_tracker"
    OTHER = "other"


@dataclass(slots=True)
class StreamDescriptor:
    stream_id: str
    name: str
    kind: StreamKind
    source_id: str | None = None
    stream_type: str | None = None
    nominal_srate: float | None = None
    channel_count: int | None = None
    sample_count: int | None = None
    origin: str | Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MarkerEvent:
    index: int
    time_s: float
    value: int | float | str
    raw_value: str
    label: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class UnifiedStreamData:
    descriptor: StreamDescriptor
    time_origin_s: float = 0.0
    marker_events: list[MarkerEvent] = field(default_factory=list)
    samples: Any | None = None
    channel_labels: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def infer_stream_kind(stream_type: str | None) -> StreamKind:
    normalized = (stream_type or "").strip().lower()
    if normalized in {"markers", "marker", "events"}:
        return StreamKind.MARKER
    if normalized in {"eeg"}:
        return StreamKind.EEG
    if normalized in {"fnirs", "nirx", "nirs"}:
        return StreamKind.FNIRS
    if normalized in {"gaze", "eye", "eyetracker", "pupil"}:
        return StreamKind.EYE_TRACKER
    return StreamKind.OTHER


def marker_value_from_raw(raw_value: Any) -> tuple[int | float | str, str | None, dict[str, Any]]:
    text = raw_value if isinstance(raw_value, str) else str(raw_value)
    try:
        payload = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return coerce_marker_scalar(text), None, {}

    if not isinstance(payload, dict):
        return coerce_marker_scalar(payload), None, {"raw_payload": payload}

    event_code = payload.get("event_code")
    event_key = payload.get("event_key") or payload.get("label")
    if event_code not in {None, "", "None"}:
        return coerce_marker_scalar(event_code), str(event_key) if event_key is not None else None, payload

    fallback = payload.get("value")
    if fallback is None:
        fallback = event_key or payload.get("description") or payload
    return coerce_marker_scalar(fallback), str(event_key) if event_key is not None else None, payload


def coerce_marker_scalar(value: Any) -> int | float | str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else value
    text = str(value).strip()
    if not text:
        return ""
    try:
        numeric = float(text)
    except ValueError:
        return text
    if numeric.is_integer():
        return int(numeric)
    return numeric


def marker_value_text(event: MarkerEvent) -> str:
    value = event.value
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def print_stream_summary(streams: list[StreamDescriptor]) -> None:
    if not streams:
        print("未发现可用 streams。")
        return
    print("可用 streams:")
    for index, descriptor in enumerate(streams, start=1):
        source_id = descriptor.source_id or "-"
        stream_type = descriptor.stream_type or descriptor.kind.value
        sample_count = descriptor.sample_count if descriptor.sample_count is not None else "-"
        channel_count = descriptor.channel_count if descriptor.channel_count is not None else "-"
        print(
            f"  [{index}] {descriptor.name} | kind={descriptor.kind.value} | type={stream_type} | "
            f"source_id={source_id} | channels={channel_count} | samples={sample_count}"
        )
