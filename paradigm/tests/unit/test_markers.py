import unittest

from psychopy import core

from paradigm.config import FNIRSConfig, MarkerConfig
from paradigm.hardware.markers import LSLMarkerBackend, MarkerManager, PsychoPyParallelLPTBackend, VirtualLPTPort, resolve_parallel_port_factory
import paradigm.hardware.markers.manager as marker_manager_module
from paradigm.hardware.markers.backends import InpOutLPTBackend, build_lpt_backend


class FakePsychoPyPort:
    def __init__(self, address: int) -> None:
        self.address = address
        self.writes: list[int] = []

    def setData(self, value: int) -> None:
        self.writes.append(int(value))


class FakeInjectedPort:
    def __init__(self, address: int) -> None:
        self.address = address
        self.writes: list[int] = []

    def set_data(self, value: int) -> None:
        self.writes.append(int(value))


class FakeTimer:
    def __init__(self, interval_s: float, callback) -> None:
        self.interval_s = interval_s
        self.callback = callback
        self.started = False
        self.cancelled = False

    def start(self) -> None:
        self.started = True
        self.callback()

    def cancel(self) -> None:
        self.cancelled = True


class FakeInpOutDLL:
    def __init__(self, *, open_ok: bool = True) -> None:
        self._open_ok = open_ok
        self.writes: list[tuple[int, int]] = []
        self.IsInpOutDriverOpen = lambda: self._open_ok

        def out32(address: int, value: int) -> None:
            self.writes.append((int(address), int(value)))

        self.Out32 = out32


class ParallelPortFactoryTests(unittest.TestCase):
    def test_resolve_parallel_port_factory_prefers_parallel_port(self) -> None:
        class Module:
            ParallelPort = FakePsychoPyPort

        factory, name = resolve_parallel_port_factory(Module)
        self.assertIsNotNone(factory)
        self.assertEqual(name, "ParallelPort")
        port = factory(0x0378)
        port.set_data(9)
        self.assertEqual(port._port.writes, [9])

    def test_resolve_parallel_port_factory_reports_missing_api(self) -> None:
        class Module:
            pass

        factory, name = resolve_parallel_port_factory(Module)
        self.assertIsNone(factory)
        self.assertEqual(name, "parallel_api_missing")


class LPTMarkerBackendTests(unittest.TestCase):
    def test_disabled_backend_does_not_send(self) -> None:
        backend = PsychoPyParallelLPTBackend(MarkerConfig(enable_lpt=False))
        self.assertFalse(backend.send(5))

    def test_send_pulses_and_clears(self) -> None:
        config = MarkerConfig(enable_lpt=True, lpt_pulse_width_ms=5.0)
        backend = PsychoPyParallelLPTBackend(config, port_factory=FakeInjectedPort, timer_factory=lambda interval, callback: FakeTimer(interval, callback))

        self.assertTrue(backend.send(42))
        self.assertEqual(backend.port.writes, [0, 42, 0])

    def test_send_rejects_out_of_range_codes(self) -> None:
        config = MarkerConfig(enable_lpt=True)
        backend = PsychoPyParallelLPTBackend(config, port_factory=FakeInjectedPort)
        with self.assertRaises(ValueError):
            backend.send(999)

    def test_reports_missing_backend_when_parallel_api_unavailable(self) -> None:
        class Module:
            pass

        backend = PsychoPyParallelLPTBackend(MarkerConfig(enable_lpt=True), parallel_module=Module)
        self.assertEqual(backend.status, "unavailable")
        self.assertEqual(backend.failure_reason, "parallel_api_missing")

    def test_build_lpt_backend_auto_falls_back_to_psychopy_when_inpout_unavailable(self) -> None:
        class Module:
            ParallelPort = FakePsychoPyPort

        backend = build_lpt_backend(
            MarkerConfig(enable_lpt=True, lpt_backend="auto"),
            parallel_module=Module,
            system_name="Darwin",
        )

        self.assertEqual(backend.backend_name, "psychopy")
        self.assertEqual(backend.status, "ready")

    def test_inpout_backend_pulses_and_clears(self) -> None:
        fake_dll = FakeInpOutDLL(open_ok=True)
        backend = InpOutLPTBackend(
            MarkerConfig(enable_lpt=True, lpt_backend="inpout", lpt_pulse_width_ms=5.0),
            timer_factory=lambda interval, callback: FakeTimer(interval, callback),
            dll_loader=lambda path: fake_dll,
            system_name="Windows",
        )

        self.assertTrue(backend.send(42))
        self.assertGreaterEqual(len(fake_dll.writes), 3)
        self.assertEqual(fake_dll.writes[0][1], 0)
        self.assertEqual(fake_dll.writes[1][1], 42)
        self.assertEqual(fake_dll.writes[2][1], 0)

    def test_virtual_port_retained_for_testing(self) -> None:
        port = VirtualLPTPort(0x0378)
        port.set_data(7)
        self.assertEqual(port.writes, [7])


class MarkerManagerTests(unittest.TestCase):
    def test_marker_manager_builds_payload_and_status(self) -> None:
        config = MarkerConfig(enable_lsl=False, enable_lpt=True)
        manager = MarkerManager(config, core.MonotonicClock(), fnirs_config=FNIRSConfig(enable_namespace=True), task_name="doors")
        manager.lpt_backend = PsychoPyParallelLPTBackend(config, port_factory=FakeInjectedPort, timer_factory=lambda interval, callback: FakeTimer(interval, callback))

        result = manager.send(12, label="choice", metadata={"task": "doors", "trial": 3})

        self.assertEqual(result.code, 12)
        self.assertEqual(result.label, "choice")
        self.assertEqual(result.payload["task"], "doors")
        self.assertEqual(result.payload["trial"], 3)
        self.assertFalse(result.lsl_sent)
        self.assertTrue(result.lpt_sent)
        self.assertFalse(result.fnirs_sent)
        status = manager.status_snapshot()
        self.assertTrue(status["fnirs_enabled"])
        self.assertEqual(status["fnirs_mode"], "lsl_namespace_only")
        self.assertEqual(status["fnirs_protocol_adapter"], "not_implemented")
        self.assertEqual(status["lpt_requested_backend"], "auto")
        self.assertEqual(status["lpt_resolved_backend"], "psychopy")

    def test_marker_manager_reports_lsl_consumers_when_backend_supports_it(self) -> None:
        config = MarkerConfig(enable_lsl=False, enable_lpt=False)
        manager = MarkerManager(config, core.MonotonicClock(), task_name="doors")

        class FakeOutlet:
            def have_consumers(self) -> bool:
                return True

        manager.lsl_backend.outlet = FakeOutlet()
        self.assertTrue(manager.lsl_have_consumers())


class LSLBackendFailureTests(unittest.TestCase):
    def test_lsl_backend_captures_stream_creation_failure(self) -> None:
        config = MarkerConfig(enable_lsl=True)
        original_outlet = marker_manager_module.StreamOutlet

        class BrokenOutlet:
            def __init__(self, info) -> None:
                raise RuntimeError("boom")

        marker_manager_module.StreamOutlet = BrokenOutlet
        try:
            backend = LSLMarkerBackend(config)
        finally:
            marker_manager_module.StreamOutlet = original_outlet

        self.assertTrue(backend.status.startswith("error:"))
