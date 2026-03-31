import json
import threading
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any, Callable, Protocol

from psychopy import core, logging
from psychopy import parallel as psychopy_parallel
from pylsl import StreamInfo, StreamOutlet, cf_string

from paradigm.config import FNIRSConfig, MarkerConfig


class ParallelPortLike(Protocol):
    def set_data(self, value: int) -> None:
        ...


TimerFactory = Callable[[float, Callable[[], None]], Any]
PortFactory = Callable[[int], ParallelPortLike]


class VirtualLPTPort:
    def __init__(self, address: int) -> None:
        self.address = address
        self.writes: list[int] = []

    def set_data(self, value: int) -> None:
        self.writes.append(int(value))


class PsychoPyParallelPortAdapter:
    def __init__(self, address: int, constructor: Callable[[int], Any]) -> None:
        self.address = address
        self._port = constructor(address)

    def set_data(self, value: int) -> None:
        self._port.setData(int(value))


@dataclass(slots=True)
class MarkerResult:
    code: int
    label: str | None
    local_time: float
    lsl_sent: bool
    lpt_sent: bool
    fnirs_sent: bool
    payload: dict[str, Any] = field(default_factory=dict)


def _default_timer_factory(interval_s: float, callback: Callable[[], None]) -> threading.Timer:
    timer = threading.Timer(interval_s, callback)
    timer.daemon = True
    return timer


def resolve_parallel_port_factory(module: ModuleType | None = None) -> tuple[PortFactory | None, str]:
    resolved_module = psychopy_parallel if module is None else module
    if resolved_module is None:
        return None, "parallel_unavailable"

    for candidate in ("ParallelPort", "Parallel"):
        constructor = getattr(resolved_module, candidate, None)
        if constructor is not None:
            return lambda address, constructor=constructor: PsychoPyParallelPortAdapter(address, constructor), candidate
    return None, "parallel_api_missing"


class LSLMarkerBackend:
    def __init__(self, config: MarkerConfig) -> None:
        self.config = config
        self.outlet = None
        self.status = "disabled"
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


class LPTMarkerBackend:
    def __init__(
        self,
        config: MarkerConfig,
        *,
        port_factory: PortFactory | None = None,
        timer_factory: TimerFactory | None = None,
        parallel_module: ModuleType | None = None,
    ) -> None:
        self.config = config
        self.port = None
        self.status = "disabled"
        self.driver_name = "disabled"
        self._pulse_timer = None
        self._lock = threading.RLock()
        self._timer_factory = timer_factory or _default_timer_factory

        if not config.enable_lpt:
            return

        resolved_port_factory = port_factory
        if resolved_port_factory is None:
            resolved_port_factory, backend_name = resolve_parallel_port_factory(parallel_module)
            self.driver_name = f"psychopy.{backend_name}" if resolved_port_factory is not None else backend_name
        else:
            self.driver_name = "injected"

        if resolved_port_factory is None:
            self.status = self.driver_name
            return

        try:
            self.port = resolved_port_factory(config.lpt_address)
            self._write_data(0)
            self.status = "ready"
        except Exception as exc:  # pragma: no cover
            self.status = f"error:{exc.__class__.__name__}"
            self.port = None

    def _write_data(self, value: int) -> None:
        if self.port is None:
            return
        self.port.set_data(int(value))

    def _clear_locked(self) -> None:
        if self.port is None:
            return
        try:
            self._write_data(0)
        finally:
            self._pulse_timer = None

    def _clear(self) -> None:
        with self._lock:
            self._clear_locked()

    def send(self, code: int) -> bool:
        if self.port is None:
            return False
        if not 0 <= int(code) <= 255:
            raise ValueError("LPT marker code must be between 0 and 255")

        try:
            with self._lock:
                self._write_data(int(code))
                pulse_width_s = max(self.config.lpt_pulse_width_ms, 0.0) / 1000.0
                if pulse_width_s > 0:
                    if self._pulse_timer is not None:
                        self._pulse_timer.cancel()
                    self._pulse_timer = self._timer_factory(pulse_width_s, self._clear)
                    self._pulse_timer.start()
                else:
                    self._clear_locked()
            return True
        except Exception as exc:  # pragma: no cover
            logging.error("LPT marker send failed: %s", exc)
            return False

    def close(self) -> None:
        with self._lock:
            if self._pulse_timer is not None:
                self._pulse_timer.cancel()
                self._pulse_timer = None
            if self.config.lpt_reset_on_close:
                self._clear_locked()
            self.port = None



class MarkerManager:
    def __init__(self, config: MarkerConfig, global_clock: core.MonotonicClock, fnirs_config: FNIRSConfig | None = None, task_name: str | None = None) -> None:
        self.config = config
        self.global_clock = global_clock
        self.fnirs_config = fnirs_config
        self.task_name = task_name
        self.lsl_backend = LSLMarkerBackend(config)
        self.lpt_backend = LPTMarkerBackend(config)

    def _fnirs_code(self, code: int) -> int | None:
        # Current fNIRS support is a stable namespace/logging layer on top of LSL payloads,
        # not a dedicated vendor protocol adapter.
        if self.fnirs_config is None or not self.fnirs_config.enable_namespace or self.task_name is None:
            return None
        task_offset = self.fnirs_config.task_offsets.get(self.task_name, 0)
        return int(self.fnirs_config.prefix * 100 + task_offset + code)

    def fnirs_code_for(self, code: int) -> int | None:
        return self._fnirs_code(code)

    def lsl_have_consumers(self) -> bool | None:
        return self.lsl_backend.have_consumers()

    def status_snapshot(self) -> dict[str, Any]:
        fnirs_enabled = bool(self.fnirs_config and self.fnirs_config.enable_namespace)
        return {
            "lsl_enabled": self.config.enable_lsl,
            "lsl_status": self.lsl_backend.status,
            "lpt_enabled": self.config.enable_lpt,
            "lpt_status": self.lpt_backend.status,
            "lpt_driver": self.lpt_backend.driver_name,
            "lpt_address": self.config.lpt_address,
            "lsl_stream_name": self.config.lsl_stream_name,
            "lsl_stream_type": self.config.lsl_stream_type,
            "fnirs_enabled": fnirs_enabled,
            "fnirs_mode": "lsl_namespace_only" if fnirs_enabled else "disabled",
            "fnirs_protocol_adapter": "not_implemented" if fnirs_enabled else "not_configured",
        }

    def _build_payload(
        self,
        code: int,
        label: str | None,
        metadata: dict[str, Any] | None,
    ) -> tuple[float, dict[str, Any]]:
        local_time = self.global_clock.getTime()
        payload = {
            "code": int(code),
            "label": label,
            "timestamp": local_time,
        }
        if metadata:
            payload.update(metadata)
        return local_time, payload

    def send(
        self,
        code: int,
        label: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MarkerResult:
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

    def send_on_flip(
        self,
        win: Any,
        code: int,
        label: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        win.callOnFlip(self.send, code, label, metadata)

    def close(self) -> None:
        self.lsl_backend.close()
        self.lpt_backend.close()
