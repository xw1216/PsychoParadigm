import unittest

from psychopy import core

from paradigm.config import FNIRSConfig, MarkerConfig
import paradigm.runtime.markers as markers_module
from paradigm.runtime.markers import LPTMarkerBackend, LSLMarkerBackend, MarkerManager, VirtualLPTPort, resolve_parallel_port_factory


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
        backend = LPTMarkerBackend(MarkerConfig(enable_lpt=False))
        self.assertFalse(backend.send(5))

    def test_send_pulses_and_clears(self) -> None:
        config = MarkerConfig(enable_lpt=True, lpt_pulse_width_ms=5.0)
        backend = LPTMarkerBackend(config, port_factory=FakeInjectedPort, timer_factory=lambda interval, callback: FakeTimer(interval, callback))

        self.assertTrue(backend.send(42))
        self.assertEqual(backend.port.writes, [0, 42, 0])

    def test_send_rejects_out_of_range_codes(self) -> None:
        config = MarkerConfig(enable_lpt=True)
        backend = LPTMarkerBackend(config, port_factory=FakeInjectedPort)
        with self.assertRaises(ValueError):
            backend.send(999)

    def test_reports_missing_backend_when_parallel_api_unavailable(self) -> None:
        class Module:
            pass

        backend = LPTMarkerBackend(MarkerConfig(enable_lpt=True), parallel_module=Module)
        self.assertEqual(backend.status, "parallel_api_missing")

    def test_virtual_port_retained_for_testing(self) -> None:
        port = VirtualLPTPort(0x0378)
        port.set_data(7)
        self.assertEqual(port.writes, [7])


class MarkerManagerTests(unittest.TestCase):
    def test_marker_manager_builds_payload_and_status(self) -> None:
        config = MarkerConfig(enable_lsl=False, enable_lpt=True)
        manager = MarkerManager(config, core.MonotonicClock(), fnirs_config=FNIRSConfig(enable_namespace=True), task_name="doors")
        manager.lpt_backend = LPTMarkerBackend(config, port_factory=FakeInjectedPort, timer_factory=lambda interval, callback: FakeTimer(interval, callback))

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
        original_outlet = markers_module.StreamOutlet

        class BrokenOutlet:
            def __init__(self, info) -> None:
                raise RuntimeError("boom")

        markers_module.StreamOutlet = BrokenOutlet
        try:
            backend = LSLMarkerBackend(config)
        finally:
            markers_module.StreamOutlet = original_outlet

        self.assertTrue(backend.status.startswith("error:"))
