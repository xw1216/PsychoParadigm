import json
import random
from typing import Any, Callable

from psychopy import core

from paradigm.config import AppConfig, DEFAULT_CONFIG
from paradigm.contracts import build_event_codebook_snapshot, get_event_definition
from paradigm.data.logging import write_frame_intervals
from paradigm.hardware.eyetracking import AOIRegion
from paradigm.hardware.markers import MarkerResult
from paradigm.runtime.session import create_experiment_session
from paradigm.utils.randomization import sample_jitter
from paradigm.utils.time import iso_timestamp


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
        self.services = create_experiment_session(
            task_name=self.task_name,
            participant=self.participant,
            session=self.session,
            config=self.config,
        )
        self.global_clock = self.services.global_clock
        self.experiment_clock = self.services.experiment_clock
        self.paths = self.services.paths
        self.event_logger = self.services.event_logger
        self.trial_logger = self.services.trial_logger
        self.marker_manager = self.services.marker_manager
        self.window = self.services.window
        self.keyboard = self.services.keyboard
        self.frame_rate_estimate = self.services.frame_rate_estimate
        self.default_text = self.services.default_text
        self.fixation = self.services.fixation
        self.text_font = self.services.text_font_request
        self.eye_tracker_manager = self.services.eye_tracker_manager
        self.eye_tracker_status = self.services.eye_tracker_manager.status
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

    def _window_info(self) -> dict[str, Any]:
        return self.services.window_info()

    def _write_metadata_snapshot(self) -> None:
        self.services.write_metadata_snapshot(
            started_at=self.started_at,
            finished_at=self.finished_at,
            final_status=self.final_status,
            event_codebook=self.event_codebook,
            run_summary=self.run_summary,
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
        event_abs_time = self._resolve_event_abs_time(marker_result=marker_result, flip_time=flip_time)
        self.event_logger.log(
            abs_time=event_abs_time,
            task_time=self.global_time_to_task_time(event_abs_time),
            task=self.task_name,
            block=block,
            trial=trial,
            event_key=resolved["event_key"],
            event_code=marker_result.code if marker_result else resolved["event_code"],
            flip_time=self.core_time_to_global_time(flip_time),
            lsl_sent=marker_result.lsl_sent if marker_result else None,
            lpt_sent=marker_result.lpt_sent if marker_result else None,
            fnirs_sent=marker_result.fnirs_sent if marker_result else None,
            extra_metadata=extra_metadata,
        )

    def _core_clock_offset(self, clock: Any) -> float:
        return core.getTime() - clock.getTime()

    def core_time_to_global_time(self, clock_time: float | None) -> float | None:
        if clock_time is None or clock_time < 0:
            return None
        return clock_time - self._core_clock_offset(self.global_clock)

    def global_time_to_task_time(self, global_time: float | None) -> float | None:
        if global_time is None or global_time < 0:
            return None
        return global_time - (self.global_clock.getTime() - self.experiment_clock.getTime())

    def core_time_to_task_time(self, clock_time: float | None) -> float | None:
        global_time = self.core_time_to_global_time(clock_time)
        return self.global_time_to_task_time(global_time)

    def flip_time_to_global_time(self, flip_time: float | None) -> float | None:
        return self.core_time_to_global_time(flip_time)

    def _resolve_event_abs_time(self, *, marker_result: MarkerResult | None, flip_time: float | None) -> float:
        flip_abs_time = self.core_time_to_global_time(flip_time)
        if flip_abs_time is not None:
            return flip_abs_time
        if marker_result is not None:
            return marker_result.local_time
        return self.global_clock.getTime()

    @staticmethod
    def append_marker_result_codes(
        marker_result: MarkerResult | None,
        *,
        lsl_codes: list[int],
        lpt_codes: list[int],
        fnirs_codes: list[int],
    ) -> None:
        if marker_result is None:
            return
        if marker_result.lsl_sent:
            lsl_codes.append(marker_result.code)
        if marker_result.lpt_sent:
            lpt_codes.append(marker_result.code)
        if marker_result.fnirs_sent:
            fnirs_code = marker_result.payload.get("fnirs_code")
            if fnirs_code is not None:
                fnirs_codes.append(int(fnirs_code))

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
        return self.flip_time_to_global_time(flip_time)

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
            "onset_time": self.flip_time_to_global_time(onset_flip),
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
    ) -> tuple[float | None, MarkerResult | None]:
        flip_time, marker_meta = self.flip_with_marker(
            draw_fn,
            event_code=event_code,
            label=label,
            event_name=event_name,
            block=block,
            trial=trial,
            metadata=metadata,
        )
        self.hold_until(draw_fn, deadline_s=flip_time + duration_s)
        return self.flip_time_to_global_time(flip_time), marker_meta["marker_result"]

    def sample_iti(self, time_range: tuple[float, float]) -> float:
        return sample_jitter(time_range, self.rng)

    def fnirs_code_for(self, code: int) -> int | None:
        return self.marker_manager.fnirs_code_for(code)

    def log_trial_row(self, row: dict[str, Any]) -> None:
        self.trial_logger.log_trial(row)

    def _write_practice_log_audit(self) -> None:
        from paradigm.analysis.log_audit import AUDIT_REPORT_NAME, audit_run_directory, write_audit_report

        audit_path = self.paths.run_dir / AUDIT_REPORT_NAME
        try:
            report = audit_run_directory(self.paths.run_dir)
        except Exception as exc:  # pragma: no cover
            report = {
                "run_dir": str(self.paths.run_dir),
                "task": self.task_name,
                "practice_enabled": True,
                "status": "error",
                "errors": [f"log audit failed: {exc.__class__.__name__}: {exc}"],
                "warnings": [],
                "checks": {},
            }
            audit_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            return
        write_audit_report(audit_path, report)

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
        self.event_logger.close()
        self.trial_logger.close()
        if self.config.practice.enabled:
            self._write_practice_log_audit()
        self._write_metadata_snapshot()
        self.marker_manager.close()
        self.eye_tracker_manager.close()
        self.window.close()
        core.quit()

    def run(self) -> None:
        raise NotImplementedError
