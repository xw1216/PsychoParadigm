from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from psychopy import core

from paradigm.config import FNIRSConfig, MarkerConfig
from paradigm.hardware.markers.lsl_config import ensure_lsl_environment

ensure_lsl_environment(MarkerConfig())

from pylsl import StreamInfo, StreamOutlet, cf_string
from paradigm.hardware.markers.backends import LPTBackendProtocol, build_lpt_backend


@dataclass(slots=True)
class MarkerResult:
    code: int
    label: str | None
    local_time: float
    lsl_sent: bool
    lpt_sent: bool
    fnirs_sent: bool
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LPTBackendSelection:
    requested_backend: str
    resolved_backend: str
    driver_name: str
    driver_path: str | None
    status: str
    failure_reason: str | None


class LSLMarkerBackend:
    def __init__(self, config: MarkerConfig) -> None:
        self.config = config
        self.outlet = None
        self.status = "disabled"
        self.config_path = ensure_lsl_environment(config)
        if not config.enable_lsl:
            return

        try:
            info = StreamInfo(
                name=config.lsl_stream_name,
                type=config.lsl_stream_type,
                channel_count=1,
                nominal_srate=0,
                channel_format=cf_string,
                source_id=config.lsl_source_id,
            )
            descriptor = info.desc()
            descriptor.append_child_value("format", "json")
            descriptor.append_child_value("producer", "psychopy-lib")
            self.outlet = StreamOutlet(info)
            self.status = "ready"
        except Exception as exc:  # pragma: no cover
            self.outlet = None
            self.status = f"error:{exc.__class__.__name__}"

    def send(self, payload: dict[str, Any]) -> bool:
        if self.outlet is None:
            return False
        self.outlet.push_sample([json.dumps(payload, ensure_ascii=True, sort_keys=True)])
        return True

    def have_consumers(self) -> bool | None:
        if self.outlet is None:
            return None
        try:
            return bool(self.outlet.have_consumers())
        except Exception:  # pragma: no cover
            return None

    def close(self) -> None:
        self.outlet = None


class MarkerManager:
    def __init__(self, config: MarkerConfig, global_clock: core.MonotonicClock, fnirs_config: FNIRSConfig | None = None, task_name: str | None = None) -> None:
        self.config = config
        self.global_clock = global_clock
        self.fnirs_config = fnirs_config
        self.task_name = task_name
        self.lsl_backend = LSLMarkerBackend(config)
        self.lpt_backend: LPTBackendProtocol = build_lpt_backend(config)

    def _fnirs_code(self, code: int) -> int | None:
        if self.fnirs_config is None or not self.fnirs_config.enable_namespace or self.task_name is None:
            return None
        task_offset = self.fnirs_config.task_offsets.get(self.task_name, 0)
        return int(self.fnirs_config.prefix * 100 + task_offset + code)

    def fnirs_code_for(self, code: int) -> int | None:
        return self._fnirs_code(code)

    def lsl_have_consumers(self) -> bool | None:
        return self.lsl_backend.have_consumers()

    def lpt_selection(self) -> LPTBackendSelection:
        return LPTBackendSelection(
            requested_backend=self.config.lpt_backend,
            resolved_backend=self.lpt_backend.backend_name,
            driver_name=self.lpt_backend.driver_name,
            driver_path=self.lpt_backend.driver_path,
            status=self.lpt_backend.status,
            failure_reason=self.lpt_backend.failure_reason,
        )

    def status_snapshot(self) -> dict[str, Any]:
        fnirs_enabled = bool(self.fnirs_config and self.fnirs_config.enable_namespace)
        selection = self.lpt_selection()
        return {
            "lsl_enabled": self.config.enable_lsl,
            "lsl_status": self.lsl_backend.status,
            "lpt_enabled": self.config.enable_lpt,
            "lpt_status": selection.status,
            "lpt_requested_backend": selection.requested_backend,
            "lpt_resolved_backend": selection.resolved_backend,
            "lpt_driver": selection.driver_name,
            "lpt_driver_path": selection.driver_path,
            "lpt_failure_reason": selection.failure_reason,
            "lpt_address": self.config.lpt_address,
            "lsl_stream_name": self.config.lsl_stream_name,
            "lsl_stream_type": self.config.lsl_stream_type,
            "lsl_api_config": self.lsl_backend.config_path,
            "fnirs_enabled": fnirs_enabled,
            "fnirs_mode": "lsl_namespace_only" if fnirs_enabled else "disabled",
            "fnirs_protocol_adapter": "not_implemented" if fnirs_enabled else "not_configured",
        }

    def _build_payload(self, code: int, label: str | None, metadata: dict[str, Any] | None) -> tuple[float, dict[str, Any]]:
        local_time = self.global_clock.getTime()
        payload = {
            "code": int(code),
            "label": label,
            "timestamp": local_time,
        }
        if metadata:
            payload.update(metadata)
        return local_time, payload

    def send(self, code: int, label: str | None = None, metadata: dict[str, Any] | None = None) -> MarkerResult:
        local_time, payload = self._build_payload(code=code, label=label, metadata=metadata)
        lsl_sent = self.lsl_backend.send(payload)
        lpt_sent = self.lpt_backend.send(int(code))
        fnirs_code = self._fnirs_code(int(code))
        fnirs_sent = False
        if fnirs_code is not None:
            fnirs_payload = dict(payload)
            fnirs_payload["fnirs_code"] = fnirs_code
            fnirs_payload["signal_namespace"] = "fnirs"
            fnirs_sent = self.lsl_backend.send(fnirs_payload)
            payload["fnirs_code"] = fnirs_code
        return MarkerResult(
            code=int(code),
            label=label,
            local_time=local_time,
            lsl_sent=lsl_sent,
            lpt_sent=lpt_sent,
            fnirs_sent=fnirs_sent,
            payload=payload,
        )

    def send_on_flip(self, win: Any, code: int, label: str | None = None, metadata: dict[str, Any] | None = None) -> None:
        win.callOnFlip(self.send, code, label, metadata)

    def close(self) -> None:
        self.lsl_backend.close()
        self.lpt_backend.close()
