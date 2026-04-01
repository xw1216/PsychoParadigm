from __future__ import annotations

import ctypes
import platform
import threading
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Protocol

from psychopy import logging

from paradigm.config import MarkerConfig


class ParallelPortLike(Protocol):
    def set_data(self, value: int) -> None:
        ...


class LPTBackendProtocol(Protocol):
    status: str
    driver_name: str
    backend_name: str
    driver_path: str | None
    failure_reason: str | None

    def send(self, code: int) -> bool:
        ...

    def close(self) -> None:
        ...


TimerFactory = Callable[[float, Callable[[], None]], Any]
PortFactory = Callable[[int], ParallelPortLike]
DLLLoader = Callable[[str], Any]


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


def _default_timer_factory(interval_s: float, callback: Callable[[], None]) -> threading.Timer:
    timer = threading.Timer(interval_s, callback)
    timer.daemon = True
    return timer


def _import_psychopy_parallel() -> ModuleType | None:
    try:
        from psychopy import parallel as psychopy_parallel
    except Exception:
        return None
    return psychopy_parallel


def resolve_parallel_port_factory(module: ModuleType | None = None) -> tuple[PortFactory | None, str]:
    resolved_module = _import_psychopy_parallel() if module is None else module
    if resolved_module is None:
        return None, "parallel_unavailable"

    for candidate in ("ParallelPort", "Parallel"):
        constructor = getattr(resolved_module, candidate, None)
        if constructor is not None:
            return lambda address, constructor=constructor: PsychoPyParallelPortAdapter(address, constructor), candidate
    return None, "parallel_api_missing"


def _validate_marker_code(code: int) -> int:
    normalized = int(code)
    if not 0 <= normalized <= 255:
        raise ValueError("LPT marker code must be between 0 and 255")
    return normalized


class NullLPTBackend:
    def __init__(
        self,
        *,
        status: str = "disabled",
        backend_name: str = "disabled",
        driver_name: str = "disabled",
        driver_path: str | None = None,
        failure_reason: str | None = None,
    ) -> None:
        self.status = status
        self.backend_name = backend_name
        self.driver_name = driver_name
        self.driver_path = driver_path
        self.failure_reason = failure_reason

    def send(self, code: int) -> bool:
        _validate_marker_code(code)
        return False

    def close(self) -> None:
        return None


class _PulseLPTBackendBase:
    def __init__(self, config: MarkerConfig, *, backend_name: str, driver_name: str) -> None:
        self.config = config
        self.backend_name = backend_name
        self.driver_name = driver_name
        self.driver_path: str | None = None
        self.failure_reason: str | None = None
        self.status = "disabled"
        self._pulse_timer = None
        self._lock = threading.RLock()
        self._timer_factory = _default_timer_factory

    def _write_data(self, value: int) -> None:
        raise NotImplementedError

    def _clear_locked(self) -> None:
        try:
            self._write_data(0)
        finally:
            self._pulse_timer = None

    def _clear(self) -> None:
        with self._lock:
            self._clear_locked()

    def send(self, code: int) -> bool:
        normalized = _validate_marker_code(code)
        if self.status != "ready":
            return False
        try:
            with self._lock:
                self._write_data(normalized)
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
            if self.status == "ready" and self.config.lpt_reset_on_close:
                self._clear_locked()


class PsychoPyParallelLPTBackend(_PulseLPTBackendBase):
    def __init__(
        self,
        config: MarkerConfig,
        *,
        port_factory: PortFactory | None = None,
        timer_factory: TimerFactory | None = None,
        parallel_module: ModuleType | None = None,
    ) -> None:
        super().__init__(config, backend_name="psychopy", driver_name="psychopy.disabled")
        self.port = None
        self._timer_factory = timer_factory or _default_timer_factory
        if not config.enable_lpt:
            return

        resolved_port_factory = port_factory
        if resolved_port_factory is None:
            resolved_port_factory, backend_name = resolve_parallel_port_factory(parallel_module)
            self.driver_name = f"psychopy.{backend_name}" if resolved_port_factory is not None else backend_name
        else:
            self.driver_name = "psychopy.injected"

        if resolved_port_factory is None:
            self.status = "unavailable"
            self.failure_reason = self.driver_name
            return

        try:
            self.port = resolved_port_factory(config.lpt_address)
            self._write_data(0)
            self.status = "ready"
        except Exception as exc:  # pragma: no cover
            self.status = "error"
            self.failure_reason = f"{exc.__class__.__name__}:{exc}"
            self.port = None

    def _write_data(self, value: int) -> None:
        if self.port is None:
            return
        self.port.set_data(int(value))

    def close(self) -> None:
        super().close()
        self.port = None


@dataclass(slots=True)
class DLLResolution:
    dll: Any
    path: str | None


def _vendor_search_dirs(config: MarkerConfig) -> list[Path]:
    search_dirs: list[Path] = []
    if config.lpt_driver_dir:
        search_dirs.append(Path(config.lpt_driver_dir))
    search_dirs.append(Path(__file__).resolve().parent / "vendor" / "windows")
    return search_dirs


def load_inpout_dll(config: MarkerConfig, *, loader: DLLLoader | None = None, system_name: str | None = None) -> DLLResolution:
    resolved_system = platform.system() if system_name is None else system_name
    if resolved_system != "Windows":
        raise RuntimeError("inpout backend requires Windows")

    resolved_loader = ctypes.WinDLL if loader is None else loader
    candidate_paths: list[Path] = []
    for directory in _vendor_search_dirs(config):
        candidate_paths.append(directory / config.lpt_dll_name)
    candidate_paths.append(Path(config.lpt_dll_name))

    for candidate in candidate_paths:
        if candidate.exists():
            return DLLResolution(dll=resolved_loader(str(candidate.resolve())), path=str(candidate.resolve()))

    try:
        return DLLResolution(dll=resolved_loader(config.lpt_dll_name), path=None)
    except OSError as exc:
        raise RuntimeError(
            f"Unable to load {config.lpt_dll_name}. Place the DLL in {', '.join(str(path) for path in _vendor_search_dirs(config))} or add it to PATH."
        ) from exc


class InpOutLPTBackend(_PulseLPTBackendBase):
    def __init__(
        self,
        config: MarkerConfig,
        *,
        timer_factory: TimerFactory | None = None,
        dll_loader: DLLLoader | None = None,
        system_name: str | None = None,
    ) -> None:
        super().__init__(config, backend_name="inpout", driver_name="inpout")
        self._timer_factory = timer_factory or _default_timer_factory
        self._out32 = None
        if not config.enable_lpt:
            return
        try:
            resolution = load_inpout_dll(config, loader=dll_loader, system_name=system_name)
            self.driver_path = resolution.path
            dll = resolution.dll
            is_driver_open = dll.IsInpOutDriverOpen
            is_driver_open.restype = ctypes.c_bool
            if not is_driver_open():
                self.status = "unavailable"
                self.failure_reason = "inpout_driver_not_open"
                return
            out32 = dll.Out32
            out32.argtypes = [ctypes.c_short, ctypes.c_short]
            out32.restype = None
            self._out32 = out32
            self._write_data(0)
            self.status = "ready"
        except Exception as exc:
            self.status = "unavailable"
            self.failure_reason = f"{exc.__class__.__name__}:{exc}"

    def _write_data(self, value: int) -> None:
        if self._out32 is None:
            return
        self._out32(self.config.lpt_address, int(value) & 0xFF)

    def close(self) -> None:
        super().close()
        self._out32 = None


@dataclass(slots=True)
class BackendBuildContext:
    port_factory: PortFactory | None = None
    timer_factory: TimerFactory | None = None
    parallel_module: ModuleType | None = None
    dll_loader: DLLLoader | None = None
    system_name: str | None = None


def build_lpt_backend(
    config: MarkerConfig,
    *,
    port_factory: PortFactory | None = None,
    timer_factory: TimerFactory | None = None,
    parallel_module: ModuleType | None = None,
    dll_loader: DLLLoader | None = None,
    system_name: str | None = None,
) -> LPTBackendProtocol:
    if not config.enable_lpt:
        return NullLPTBackend()

    context = BackendBuildContext(
        port_factory=port_factory,
        timer_factory=timer_factory,
        parallel_module=parallel_module,
        dll_loader=dll_loader,
        system_name=system_name,
    )
    attempts: list[tuple[str, Callable[[], LPTBackendProtocol]]] = []
    if config.lpt_backend == "inpout":
        attempts.append(("inpout", lambda: InpOutLPTBackend(config, timer_factory=context.timer_factory, dll_loader=context.dll_loader, system_name=context.system_name)))
    elif config.lpt_backend == "psychopy":
        attempts.append(("psychopy", lambda: PsychoPyParallelLPTBackend(config, port_factory=context.port_factory, timer_factory=context.timer_factory, parallel_module=context.parallel_module)))
    else:
        attempts.extend(
            [
                ("inpout", lambda: InpOutLPTBackend(config, timer_factory=context.timer_factory, dll_loader=context.dll_loader, system_name=context.system_name)),
                ("psychopy", lambda: PsychoPyParallelLPTBackend(config, port_factory=context.port_factory, timer_factory=context.timer_factory, parallel_module=context.parallel_module)),
            ]
        )

    failures: list[str] = []
    for name, builder in attempts:
        backend = builder()
        if backend.status == "ready":
            return backend
        failures.append(f"{name}:{backend.failure_reason or backend.status}")
        if config.lpt_backend != "auto":
            return backend

    return NullLPTBackend(
        status="unavailable",
        backend_name="disabled",
        driver_name="none",
        failure_reason="; ".join(failures) if failures else "no_backend_attempted",
    )
