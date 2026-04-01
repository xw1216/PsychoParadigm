from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psychopy
from psychopy import core
from psychopy import visual
from psychopy.hardware import keyboard

from paradigm.config import AppConfig
from paradigm.contracts import build_event_codebook_schema, get_run_summary_schema, get_task_specific_data_schema
from paradigm.data.logging import EventLogger, TrialLogger, write_metadata
from paradigm.hardware.eyetracking import EyeTrackerManager
from paradigm.hardware.markers import MarkerManager
from paradigm.utils.paths import ensure_directory
from paradigm.utils.time import timestamp_for_path


@dataclass(slots=True)
class ExperimentPaths:
    run_dir: Path
    metadata_path: Path
    event_log_path: Path
    trial_log_path: Path
    frame_interval_path: Path


@dataclass(slots=True)
class ExperimentSession:
    task_name: str
    participant: str
    session: str
    config: AppConfig
    paths: ExperimentPaths
    global_clock: core.MonotonicClock
    experiment_clock: core.Clock
    event_logger: EventLogger
    trial_logger: TrialLogger
    marker_manager: MarkerManager
    window: Any
    keyboard: Any
    default_text: Any
    fixation: Any
    eye_tracker_manager: EyeTrackerManager
    frame_rate_estimate: float | None

    def window_info(self) -> dict[str, Any]:
        return {
            "size": list(self.window.size),
            "fullscr": self.window._isFullScr,
            "monitor_name": self.config.screen.monitor_name,
            "units": self.config.screen.units,
            "color": list(self.config.screen.color),
        }

    def write_metadata_snapshot(
        self,
        *,
        started_at: str,
        finished_at: str | None,
        final_status: str,
        event_codebook: dict[str, Any],
        run_summary: dict[str, Any],
    ) -> None:
        write_metadata(
            self.paths.metadata_path,
            participant=self.participant,
            session=self.session,
            task_name=self.task_name,
            config=self.config,
            started_at=started_at,
            psychopy_version=psychopy.__version__,
            marker_status=self.marker_manager.status_snapshot(),
            frame_rate_estimate=self.frame_rate_estimate,
            window_info=self.window_info(),
            extra={
                "eye_tracker": self.eye_tracker_manager.status_snapshot(),
                "finished_at": finished_at,
                "final_status": final_status,
                "run_mode": "practice" if self.config.practice.enabled else "main",
                "event_codebook": event_codebook,
                "event_codebook_schema": build_event_codebook_schema(),
                "task_specific_data_schema": get_task_specific_data_schema(self.task_name),
                "run_summary_schema": get_run_summary_schema(self.task_name),
                "run_summary": run_summary,
            },
        )


def build_experiment_paths(config: AppConfig, *, participant: str, session: str, task_name: str) -> ExperimentPaths:
    run_id = timestamp_for_path()
    run_dir = ensure_directory(config.data_root() / f"sub-{participant}" / f"ses-{session}" / task_name / run_id)
    return ExperimentPaths(
        run_dir=run_dir,
        metadata_path=run_dir / config.data.metadata_name,
        event_log_path=run_dir / config.data.event_log_name,
        trial_log_path=run_dir / config.data.trial_log_name,
        frame_interval_path=run_dir / config.data.frame_interval_name,
    )


def create_experiment_session(*, task_name: str, participant: str, session: str, config: AppConfig) -> ExperimentSession:
    paths = build_experiment_paths(config, participant=participant, session=session, task_name=task_name)
    global_clock = core.MonotonicClock()
    experiment_clock = core.Clock()
    event_logger = EventLogger(paths.event_log_path, flush_every_event=config.logging.flush_every_event)
    trial_logger = TrialLogger(paths.trial_log_path, flush_every_event=config.logging.flush_every_event)
    marker_manager = MarkerManager(config.markers, global_clock, fnirs_config=config.fnirs, task_name=task_name)
    window = visual.Window(
        size=config.screen.size,
        fullscr=config.screen.fullscr,
        monitor=config.screen.monitor_name,
        units=config.screen.units,
        color=config.screen.color,
        allowGUI=config.screen.allow_gui,
        waitBlanking=config.screen.wait_blank,
        useFBO=True,
    )
    keyboard_device = keyboard.Keyboard()
    frame_rate_result = window.getActualFrameRate(
        nIdentical=20,
        nMaxFrames=240,
        nWarmUpFrames=20,
        threshold=1,
    )
    frame_rate_estimate = float(frame_rate_result) if frame_rate_result is not None else None
    window.recordFrameIntervals = config.screen.record_frame_intervals
    default_text = visual.TextStim(win=window, text="", color="white", height=0.04, wrapWidth=1.4)
    fixation = visual.TextStim(win=window, text="+", color="white", height=0.05)
    eye_tracker_manager = EyeTrackerManager(config.eye_tracker, config.screen)
    return ExperimentSession(
        task_name=task_name,
        participant=participant,
        session=session,
        config=config,
        paths=paths,
        global_clock=global_clock,
        experiment_clock=experiment_clock,
        event_logger=event_logger,
        trial_logger=trial_logger,
        marker_manager=marker_manager,
        window=window,
        keyboard=keyboard_device,
        default_text=default_text,
        fixation=fixation,
        eye_tracker_manager=eye_tracker_manager,
        frame_rate_estimate=frame_rate_estimate,
    )
