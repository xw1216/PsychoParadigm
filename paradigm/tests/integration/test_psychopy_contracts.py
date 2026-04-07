import unittest
from unittest.mock import patch

import paradigm.runtime.base_experiment as base_experiment_module
from paradigm.runtime.base_experiment import BaseExperiment
from paradigm.hardware.eyetracking import AOIRegion
from paradigm.hardware.markers import MarkerResult


class FakeClock:
    def __init__(self) -> None:
        self.reset_count = 0

    def reset(self) -> None:
        self.reset_count += 1

    def getTime(self) -> float:
        return 0.0


class FixedClock:
    def __init__(self, time_value: float) -> None:
        self.time_value = time_value

    def getTime(self) -> float:
        return self.time_value


class FakeKeyboard:
    def __init__(self) -> None:
        self.clock = FakeClock()
        self.clear_count = 0

    def clearEvents(self) -> None:
        self.clear_count += 1


class FakeWindow:
    def __init__(self) -> None:
        self._queued: list[tuple] = []
        self.flip_count = 0

    def callOnFlip(self, callback, *args) -> None:
        self._queued.append((callback, args))

    def flip(self) -> float:
        self.flip_count += 1
        queued = list(self._queued)
        self._queued.clear()
        for callback, args in queued:
            callback(*args)
        return 100.0 + self.flip_count


class FakeMarkerManager:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str | None, dict | None]] = []

    def send(self, code: int, label: str | None = None, metadata: dict | None = None) -> MarkerResult:
        payload = dict(metadata or {})
        if metadata and "fnirs_code" in metadata:
            payload["fnirs_code"] = metadata["fnirs_code"]
        self.calls.append((code, label, metadata))
        return MarkerResult(code=code, label=label, local_time=1.23, lsl_sent=True, lpt_sent=True, fnirs_sent=False, payload=payload)


class FakeEyeTrackerManager:
    def __init__(self) -> None:
        self.transition = {"aoi_from": None, "aoi_to": "left", "gaze_x": -0.2, "gaze_y": 0.0}

    def detect_aoi_transition(self, aoi_regions):
        return self.transition


class CapturingEventLogger:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def log(self, **kwargs) -> None:
        self.calls.append(kwargs)


class BaseExperimentFlipContractsTests(unittest.TestCase):
    def test_flip_with_marker_sends_marker_on_flip_and_resets_keyboard_clock(self) -> None:
        experiment = BaseExperiment.__new__(BaseExperiment)
        experiment.window = FakeWindow()
        experiment.keyboard = FakeKeyboard()
        experiment.marker_manager = FakeMarkerManager()
        logged: list[dict] = []
        experiment.log_event = lambda **kwargs: logged.append(kwargs)

        draw_count = {"count": 0}

        def draw_fn() -> None:
            draw_count["count"] += 1

        flip_time, marker_meta = BaseExperiment.flip_with_marker(experiment, draw_fn, event_code=15, label="choice_onset", block=1, trial=2, metadata={"task": "doors"}, reset_keyboard_clock=True)

        self.assertEqual(draw_count["count"], 1)
        self.assertEqual(flip_time, 101.0)
        self.assertEqual(experiment.keyboard.clear_count, 1)
        self.assertEqual(experiment.keyboard.clock.reset_count, 1)
        self.assertEqual(experiment.marker_manager.calls, [(15, "choice_onset", {"task": "doors"})])
        self.assertEqual(marker_meta["marker_result"].code, 15)
        self.assertEqual(marker_meta["event_code"], 15)
        self.assertEqual(logged[0]["flip_time"], 101.0)

    def test_poll_and_log_aoi_writes_eye_tracking_event(self) -> None:
        experiment = BaseExperiment.__new__(BaseExperiment)
        experiment.task_name = "doors"
        experiment.config = type("Config", (), {"eye_tracker": type("EyeConfig", (), {"record_aoi_events": True})()})()
        experiment.eye_tracker_manager = FakeEyeTrackerManager()
        logged: list[dict] = []
        experiment.log_event = lambda **kwargs: logged.append(kwargs)
        BaseExperiment.poll_and_log_aoi(experiment, aoi_regions=[AOIRegion("left", -1.0, 0.0, -1.0, 1.0)], block=1, trial=1)
        self.assertEqual(logged[0]["event_name"], "doors.aoi.transition")

    def test_log_event_uses_flip_time_on_unified_analysis_clock(self) -> None:
        experiment = BaseExperiment.__new__(BaseExperiment)
        experiment.task_name = "doors"
        experiment.global_clock = FixedClock(5.0)
        experiment.experiment_clock = FixedClock(2.0)
        experiment.event_logger = CapturingEventLogger()
        experiment.resolve_event = lambda event_name: {"event_key": event_name, "event_code": 12}

        marker_result = MarkerResult(code=12, label="doors.choice.onset", local_time=4.25, lsl_sent=True, lpt_sent=False, fnirs_sent=False, payload={})

        with patch.object(base_experiment_module.core, "getTime", return_value=105.0):
            BaseExperiment.log_event(experiment, event_name="doors.choice.onset", marker_result=marker_result, flip_time=104.0)

        logged = experiment.event_logger.calls[0]
        self.assertAlmostEqual(logged["abs_time"], 4.0)
        self.assertAlmostEqual(logged["task_time"], 1.0)
        self.assertAlmostEqual(logged["flip_time"], 4.0)

    def test_log_event_uses_marker_local_time_when_no_flip_time_exists(self) -> None:
        experiment = BaseExperiment.__new__(BaseExperiment)
        experiment.task_name = "doors"
        experiment.global_clock = FixedClock(5.0)
        experiment.experiment_clock = FixedClock(2.0)
        experiment.event_logger = CapturingEventLogger()
        experiment.resolve_event = lambda event_name: {"event_key": event_name, "event_code": 13}

        marker_result = MarkerResult(code=13, label="doors.response.left", local_time=4.25, lsl_sent=True, lpt_sent=False, fnirs_sent=False, payload={})

        with patch.object(base_experiment_module.core, "getTime", return_value=105.0):
            BaseExperiment.log_event(experiment, event_name="doors.response.left", marker_result=marker_result, flip_time=None)

        logged = experiment.event_logger.calls[0]
        self.assertAlmostEqual(logged["abs_time"], 4.25)
        self.assertAlmostEqual(logged["task_time"], 1.25)
        self.assertIsNone(logged["flip_time"])
