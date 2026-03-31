import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import psychopy
from psychopy import core, visual
from psychopy.hardware import keyboard

from paradigm.config import AppConfig, DEFAULT_CONFIG
from paradigm.runtime.event_codes import build_event_codebook_snapshot, get_event_definition
from paradigm.runtime.eye_tracking import AOIRegion, EyeTrackerManager
from paradigm.runtime.logging_utils import EventLogger, TrialLogger, setup_psychopy_logging, write_frame_intervals, write_metadata
from paradigm.runtime.markers import MarkerManager, MarkerResult
from paradigm.runtime.schemas import build_event_codebook_schema, get_run_summary_schema, get_task_specific_data_schema
from paradigm.runtime.utils import ensure_directory, iso_timestamp, sample_jitter, timestamp_for_path


@dataclass(slots=True)
class ExperimentPaths:
    run_dir: Path
    metadata_path: Path
    event_log_path: Path
    trial_log_path: Path
    frame_interval_path: Path
    psychopy_log_path: Path | None


class SafeExitRequested(RuntimeError):
    pass


class BaseExperiment:
    def __init__(
        self,
        *,
        task_name: str,
        participant: str,
        session: str,
        config: AppConfig | None = None,
    ) -> None:
        self.task_name = task_name
        self.participant = participant
        self.session = session
        self.config = config or DEFAULT_CONFIG
        self.rng = random.Random()
        self.started_at = iso_timestamp()
        self.finished_at: str | None = None
        self.final_status = "initialized"
        self.run_summary: dict[str, Any] = {}
        self.event_codebook = build_event_codebook_snapshot()
        self.global_clock = core.MonotonicClock()
        self.experiment_clock = core.Clock()
        self.paths = self._build_paths()
        setup_psychopy_logging(self.paths.psychopy_log_path, self.config.logging.file_level)
        self.event_logger = EventLogger(self.paths.event_log_path, flush_every_event=self.config.logging.flush_every_event)
        self.trial_logger = TrialLogger(self.paths.trial_log_path, flush_every_event=self.config.logging.flush_every_event)
        self.marker_manager = MarkerManager(self.config.markers, self.global_clock, fnirs_config=self.config.fnirs, task_name=self.task_name)
        self.window = self._create_window()
        self.keyboard = keyboard.Keyboard()
        self.frame_rate_estimate = self.window.getActualFrameRate(
            nIdentical=20,
            nMaxFrames=240,
            nWarmUpFrames=20,
            threshold=1.0,
        )
        self.window.recordFrameIntervals = self.config.screen.record_frame_intervals
        self.default_text = visual.TextStim(win=self.window, text="", color="white", height=0.04, wrapWidth=1.4)
        self.fixation = visual.TextStim(win=self.window, text="+", color="white", height=0.05)
        self.eye_tracker_manager = EyeTrackerManager(self.config.eye_tracker, self.config.screen)
        self.eye_tracker_status = self.eye_tracker_manager.status
        self._write_metadata_snapshot()

    def continue_key_name(self) -> str:
        return self.config.common.continue_key.lower()

    def continue_key_label(self) -> str:
        return self.config.common.continue_key.upper()

    def force_continue_key_name(self) -> str:
        return self.config.common.force_continue_key.lower()

    def force_continue_key_label(self) -> str:
        return self.config.common.force_continue_key.upper()

    def refresh_key_name(self) -> str:
        return self.config.common.refresh_key.lower()

    def refresh_key_label(self) -> str:
        return self.config.common.refresh_key.upper()

    def _build_paths(self) -> ExperimentPaths:
        run_id = timestamp_for_path()
        run_dir = ensure_directory(self.config.data_root() / f"sub-{self.participant}" / f"ses-{self.session}" / self.task_name / run_id)
        return ExperimentPaths(
            run_dir=run_dir,
            metadata_path=run_dir / self.config.data.metadata_name,
            event_log_path=run_dir / self.config.data.event_log_name,
            trial_log_path=run_dir / self.config.data.trial_log_name,
            frame_interval_path=run_dir / self.config.data.frame_interval_name,
            psychopy_log_path=(run_dir / self.config.data.psychopy_log_name) if self.config.logging.save_psychopy_log else None,
        )

    def _create_window(self) -> visual.Window:
        fullscr = self.config.screen.fullscr
        return visual.Window(
            size=self.config.screen.size,
            fullscr=fullscr,
            monitor=self.config.screen.monitor_name,
            units=self.config.screen.units,
            color=self.config.screen.color,
            allowGUI=self.config.screen.allow_gui,
            waitBlanking=self.config.screen.wait_blank,
            useFBO=True,
        )

    def _window_info(self) -> dict[str, Any]:
        return {
            "size": list(self.window.size),
            "fullscr": self.window._isFullScr,
            "monitor_name": self.config.screen.monitor_name,
            "units": self.config.screen.units,
            "color": list(self.config.screen.color),
        }

    def _write_metadata_snapshot(self) -> None:
        write_metadata(
            self.paths.metadata_path,
            participant=self.participant,
            session=self.session,
            task_name=self.task_name,
            config=self.config,
            started_at=self.started_at,
            psychopy_version=psychopy.__version__,
            marker_status=self.marker_manager.status_snapshot(),
            frame_rate_estimate=self.frame_rate_estimate,
            window_info=self._window_info(),
            extra={
                "eye_tracker_status": self.eye_tracker_status,
                "finished_at": self.finished_at,
                "final_status": self.final_status,
                "run_mode": "practice" if self.config.practice.enabled else "main",
                "event_codebook": self.event_codebook,
                "event_codebook_schema": build_event_codebook_schema(),
                "task_specific_data_schema": get_task_specific_data_schema(self.task_name),
                "run_summary_schema": get_run_summary_schema(self.task_name),
                "run_summary": self.run_summary,
            },
        )

    def resolve_event(self, event_name: str) -> dict[str, Any]:
        definition = get_event_definition(self.task_name, event_name)
        return {
            "event_key": definition.event_key,
            "event_code": definition.event_code,
            "description": definition.description,
        }

    def build_event_metadata(self, event_name: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        resolved = self.resolve_event(event_name)
        merged = {"event_key": resolved["event_key"], "event_code": resolved["event_code"]}
        if metadata:
            merged.update(metadata)
        return merged

    def poll_and_log_aoi(self, *, aoi_regions: list[AOIRegion], block: int | None, trial: int | None) -> None:
        if not self.config.eye_tracker.record_aoi_events:
            return
        transition = self.eye_tracker_manager.detect_aoi_transition(aoi_regions)
        if transition is None:
            return
        self.log_event(
            event_name=f"{self.task_name}.aoi.transition",
            block=block,
            trial=trial,
            extra_metadata=transition,
        )

    def log_event(
        self,
        *,
        event_name: str,
        block: int | None = None,
        trial: int | None = None,
        marker_result: MarkerResult | None = None,
        flip_time: float | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> None:
        resolved = self.resolve_event(event_name)
        self.event_logger.log(
            abs_time=self.global_clock.getTime(),
            task_time=self.experiment_clock.getTime(),
            task=self.task_name,
            block=block,
            trial=trial,
            event_key=resolved["event_key"],
            event_code=marker_result.code if marker_result else resolved["event_code"],
            flip_time=flip_time,
            lsl_sent=marker_result.lsl_sent if marker_result else None,
            lpt_sent=marker_result.lpt_sent if marker_result else None,
            fnirs_sent=marker_result.fnirs_sent if marker_result else None,
            extra_metadata=extra_metadata,
        )

    def check_escape(self) -> None:
        keys = self.keyboard.getKeys(keyList=["escape"], waitRelease=False, clear=False)
        if keys:
            raise SafeExitRequested("escape pressed")

    def send_marker_now(
        self,
        *,
        event_code: int | None = None,
        label: str | None = None,
        event_name: str | None = None,
        metadata: dict[str, Any] | None = None,
        block: int | None = None,
        trial: int | None = None,
        flip_time: float | None = None,
    ) -> MarkerResult:
        if event_name is not None:
            resolved = self.resolve_event(event_name)
            event_code = resolved["event_code"]
            label = resolved["event_key"]
            metadata = self.build_event_metadata(event_name, metadata)
        assert event_code is not None
        assert label is not None
        result = self.marker_manager.send(code=event_code, label=label, metadata=metadata)
        self.log_event(
            event_name=event_name or label,
            block=block,
            trial=trial,
            marker_result=result,
            flip_time=flip_time,
            extra_metadata=metadata,
        )
        return result

    def flip_with_marker(
        self,
        draw_fn: Callable[[], None],
        *,
        event_code: int | None = None,
        label: str | None = None,
        event_name: str | None = None,
        block: int | None,
        trial: int | None,
        metadata: dict[str, Any] | None = None,
        reset_keyboard_clock: bool = False,
    ) -> tuple[float, dict[str, Any]]:
        if event_name is not None:
            resolved = self.resolve_event(event_name)
            event_code = resolved["event_code"]
            label = resolved["event_key"]
            metadata = self.build_event_metadata(event_name, metadata)
        assert event_code is not None
        assert label is not None
        marker_holder: dict[str, MarkerResult | None] = {"result": None}

        def _send_marker() -> None:
            marker_holder["result"] = self.marker_manager.send(code=event_code, label=label, metadata=metadata)

        draw_fn()
        if reset_keyboard_clock:
            self.window.callOnFlip(self.keyboard.clearEvents)
            self.window.callOnFlip(self.keyboard.clock.reset)
        self.window.callOnFlip(_send_marker)
        flip_time = self.window.flip()
        marker_result = marker_holder["result"]
        self.log_event(
            event_name=event_name or label,
            block=block,
            trial=trial,
            marker_result=marker_result,
            flip_time=flip_time,
            extra_metadata=metadata,
        )
        return flip_time, {"marker_result": marker_result, "event_code": event_code}

    def hold_until(self, draw_fn: Callable[[], None], deadline_s: float) -> None:
        while core.getTime() < deadline_s:
            self.check_escape()
            draw_fn()
            self.window.flip()

    def present_interval(self, draw_fn: Callable[[], None], duration_s: float) -> float:
        draw_fn()
        flip_time = self.window.flip()
        self.hold_until(draw_fn, deadline_s=flip_time + duration_s)
        return flip_time

    def show_message(self, text: str, wait_for_key: bool = True, key_list: list[str] | None = None) -> None:
        self.default_text.text = text
        self.keyboard.clearEvents()
        while True:
            self.check_escape()
            self.default_text.draw()
            self.window.flip()
            if not wait_for_key:
                return
            keys = self.keyboard.getKeys(keyList=key_list or [self.continue_key_name()], waitRelease=False)
            if keys:
                return

    def show_labrecorder_wait_screen(self) -> None:
        self.keyboard.clearEvents()
        while True:
            self.check_escape()
            lsl_status = self.marker_manager.lsl_backend.status
            consumer_state = self.marker_manager.lsl_have_consumers()
            if consumer_state is True:
                consumer_line = "LabRecorder 订阅状态：已检测到"
            elif consumer_state is False:
                consumer_line = "LabRecorder 订阅状态：尚未检测到"
            else:
                consumer_line = "LabRecorder 订阅状态：当前不可检测"

            continue_hint = f"检测到订阅后，按 {self.continue_key_label()} 继续。"
            if not self.config.markers.enable_lsl:
                continue_hint = f"本次运行未启用 LSL。按 {self.continue_key_label()} 继续。"

            self.default_text.text = (
                f"运行前 LSL 检查\n\n"
                f"任务：{self.task_name}\n"
                f"流名称：{self.config.markers.lsl_stream_name}\n"
                f"LSL 后端状态：{lsl_status}\n"
                f"{consumer_line}\n\n"
                f"请先打开 LabRecorder，并确认它已经订阅当前 marker 流。\n\n"
                f"{continue_hint}\n"
                f"按 {self.force_continue_key_label()} 可强制继续。\n"
                f"按 {self.refresh_key_label()} 刷新当前状态。\n"
                f"按 ESC 安全退出。"
            )
            self.default_text.draw()
            self.window.flip()
            keys = self.keyboard.getKeys(
                keyList=[self.continue_key_name(), self.force_continue_key_name(), self.refresh_key_name()],
                waitRelease=False,
            )
            if not keys:
                continue
            key_name = keys[0].name
            if key_name == self.force_continue_key_name():
                return
            if key_name == self.refresh_key_name():
                self.keyboard.clearEvents()
                continue
            if not self.config.markers.enable_lsl or consumer_state is True:
                return

    def show_break(self, *, block: int, completed_trials: int, total_trials: int) -> None:
        self.log_event(
            event_name=f"{self.task_name}.break.start",
            block=block,
            trial=completed_trials,
            extra_metadata={"completed_trials": completed_trials, "total_trials": total_trials},
        )
        self.show_message(
            f"第 {block} 个区组已结束。\n\n已完成试次：{completed_trials}/{total_trials}。\n\n按 {self.continue_key_label()} 继续。"
        )
        self.log_event(event_name=f"{self.task_name}.break.end", block=block, trial=completed_trials)

    def fixation_period(self, *, duration_s: float, event_code: int | None = None, label: str | None = None, event_name: str | None = None, block: int, trial: int) -> float:
        flip_time, _ = self.flip_with_marker(
            self.fixation.draw,
            event_code=event_code,
            label=label,
            event_name=event_name,
            block=block,
            trial=trial,
            metadata={"task": self.task_name, "block": block, "trial": trial},
        )
        self.hold_until(self.fixation.draw, deadline_s=flip_time + duration_s)
        return flip_time

    def wait_for_response(
        self,
        *,
        draw_fn: Callable[[], None],
        valid_keys: tuple[str, ...],
        timeout_s: float,
        onset_event_code: int | None,
        onset_label: str | None,
        onset_event_name: str | None,
        block: int,
        trial: int,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        onset_flip, marker_meta = self.flip_with_marker(
            draw_fn,
            event_code=onset_event_code,
            label=onset_label,
            event_name=onset_event_name,
            block=block,
            trial=trial,
            metadata=metadata,
            reset_keyboard_clock=True,
        )
        response = None
        rt = None
        response_abs = None
        deadline = self.keyboard.clock.getTime() + timeout_s
        while self.keyboard.clock.getTime() < deadline:
            self.check_escape()
            draw_fn()
            self.window.flip()
            keys = self.keyboard.getKeys(keyList=list(valid_keys), waitRelease=False)
            if keys:
                key_press = keys[0]
                response = key_press.name
                rt = key_press.rt
                response_abs = self.global_clock.getTime()
                break
        return {
            "onset_flip": onset_flip,
            "response": response,
            "rt": rt,
            "response_abs": response_abs,
            "timeout": response is None,
            "onset_marker": marker_meta["marker_result"],
        }

    def present_timed_event(
        self,
        *,
        draw_fn: Callable[[], None],
        duration_s: float,
        event_code: int | None,
        label: str | None,
        event_name: str | None,
        block: int,
        trial: int,
        metadata: dict[str, Any] | None = None,
    ) -> float:
        flip_time, _ = self.flip_with_marker(
            draw_fn,
            event_code=event_code,
            label=label,
            event_name=event_name,
            block=block,
            trial=trial,
            metadata=metadata,
        )
        self.hold_until(draw_fn, deadline_s=flip_time + duration_s)
        return flip_time

    def sample_iti(self, time_range: tuple[float, float]) -> float:
        return sample_jitter(time_range, self.rng)

    def fnirs_code_for(self, code: int) -> int | None:
        return self.marker_manager.fnirs_code_for(code)

    def log_trial_row(self, row: dict[str, Any]) -> None:
        self.trial_logger.log_trial(row)

    def finalize(self) -> None:
        self.finished_at = iso_timestamp()
        if self.config.screen.record_frame_intervals:
            frame_intervals = list(self.window.frameIntervals)
            write_frame_intervals(self.paths.frame_interval_path, frame_intervals)
            if frame_intervals:
                threshold = self.config.logging.dropped_frame_factor / (self.frame_rate_estimate or self.config.screen.target_frame_rate)
                for index, interval in enumerate(frame_intervals, start=1):
                    if interval > threshold:
                        self.log_event(
                            event_name="system.frame.dropped_warning",
                            extra_metadata={"frame_index": index, "interval_s": interval},
                        )
        self._write_metadata_snapshot()
        self.event_logger.close()
        self.trial_logger.close()
        self.marker_manager.close()
        self.eye_tracker_manager.close()
        self.window.close()
        core.quit()

    def run(self) -> None:
        raise NotImplementedError
