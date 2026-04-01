import tempfile
import unittest
from pathlib import Path

import paradigm.runtime.base_experiment as base_experiment_module
from paradigm.config import AppConfig, ScreenConfig
from paradigm.runtime.base_experiment import BaseExperiment


class FakeClosable:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeWindow(FakeClosable):
    def __init__(self) -> None:
        super().__init__()
        self.frameIntervals = []


class LifecycleTests(unittest.TestCase):
    def test_finalize_closes_resources_and_writes_metadata_snapshot(self) -> None:
        experiment = BaseExperiment.__new__(BaseExperiment)
        experiment.config = AppConfig()
        experiment.config.screen.record_frame_intervals = False
        experiment.config.logging.dropped_frame_factor = 1.5
        experiment.frame_rate_estimate = 60.0
        experiment.finished_at = None
        experiment.event_logger = FakeClosable()
        experiment.trial_logger = FakeClosable()
        experiment.marker_manager = FakeClosable()
        experiment.eye_tracker_manager = FakeClosable()
        experiment.window = FakeWindow()
        calls: list[str] = []
        experiment._write_metadata_snapshot = lambda: calls.append("metadata")

        original_quit = base_experiment_module.core.quit
        base_experiment_module.core.quit = lambda: None
        try:
            BaseExperiment.finalize(experiment)
        finally:
            base_experiment_module.core.quit = original_quit

        self.assertEqual(calls, ["metadata"])
        self.assertTrue(experiment.event_logger.closed)
        self.assertTrue(experiment.trial_logger.closed)
        self.assertTrue(experiment.marker_manager.closed)
        self.assertTrue(experiment.eye_tracker_manager.closed)
        self.assertTrue(experiment.window.closed)

    def test_eye_tracker_init_failure_sets_error_status(self) -> None:
        class BrokenEyeTrackerManager:
            def __init__(self, config, screen_config) -> None:
                self.status = "error:RuntimeError"

            def close(self) -> None:
                pass

        self.assertEqual(BrokenEyeTrackerManager(None, None).status, "error:RuntimeError")
