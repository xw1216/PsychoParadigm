from __future__ import annotations

from psychopy import core

from paradigm.config import AppConfig
from paradigm.runtime.base_experiment import BaseExperiment, SafeExitRequested
from paradigm.tasks.marker_test.marker_test_logic import build_test_marker_sequence


class MarkerTestTask(BaseExperiment):
    def __init__(self, participant: str, session: str, config: AppConfig | None = None) -> None:
        super().__init__(task_name="marker_test", participant=participant, session=session, config=config)
        self.task_config = self.config.marker_test
        self._sequence = build_test_marker_sequence(self.task_config.start_code, self.task_config.end_code)

    @staticmethod
    def _event(name: str) -> str:
        return f"marker_test.{name}"

    def _status_text(self, message: str) -> None:
        self.default_text.text = message
        self.default_text.draw()

    def _marker_message(self, *, raw_code: int, sequence_index: int, total_codes: int) -> str:
        return (
            "Marker Test\n\n"
            f"正在发送测试 marker：{raw_code}\n"
            f"进度：{sequence_index}/{total_codes}\n"
            f"当前单码维持时间：{self.task_config.interval_s:.3f} s"
        )

    def _auto_wait_for_lsl_consumer(self) -> bool | None:
        if not self.config.markers.enable_lsl:
            return False

        self.log_event(event_name=self._event("lsl_wait.start"), extra_metadata={"task": self.task_name})
        deadline = self.global_clock.getTime() + self.task_config.auto_continue_unobservable_s
        while True:
            self.check_escape()
            consumer_state = self.marker_manager.lsl_have_consumers()
            self._status_text(
                "Marker Test\n\n"
                f"LSL 后端状态：{self.marker_manager.lsl_backend.status}\n"
                f"LabRecorder 订阅检测：{consumer_state}\n\n"
                "正在自动等待 LSL 订阅端连接，无需按键。"
            )
            self.window.flip()
            if consumer_state is True:
                if self.task_config.consumer_settle_s > 0:
                    settle_deadline = self.global_clock.getTime() + self.task_config.consumer_settle_s
                    while self.global_clock.getTime() < settle_deadline:
                        self.check_escape()
                        self._status_text("Marker Test\n\n已检测到 LSL 订阅端，正在开始前短暂稳定连接。")
                        self.window.flip()
                self.log_event(event_name=self._event("lsl_wait.end"), extra_metadata={"task": self.task_name, "consumer_detected": True})
                return True
            if consumer_state is None and self.global_clock.getTime() >= deadline:
                self.log_event(event_name=self._event("lsl_wait.end"), extra_metadata={"task": self.task_name, "consumer_detected": None})
                return None

    def _send_raw_test_marker(self, *, raw_code: int, sequence_index: int, total_codes: int) -> tuple[float, object, str]:
        metadata = {
            "task": self.task_name,
            "sequence_index": sequence_index,
            "raw_marker_code": raw_code,
        }
        marker_label = f"marker_test.code.{raw_code:03d}"
        marker_message = self._marker_message(raw_code=raw_code, sequence_index=sequence_index, total_codes=total_codes)
        marker_holder: dict[str, object | None] = {"result": None}

        def _send_marker() -> None:
            marker_holder["result"] = self.marker_manager.send(code=raw_code, label=marker_label, metadata=metadata)

        self.window.callOnFlip(_send_marker)
        self._status_text(marker_message)
        flip_time = self.window.flip()
        result = marker_holder["result"]
        assert result is not None
        self.log_event(
            event_name=self._event("pulse"),
            block=1,
            trial=sequence_index,
            marker_result=result,
            flip_time=flip_time,
            extra_metadata={**metadata, "marker_label": marker_label},
        )
        return flip_time, result, marker_message

    def run(self) -> None:
        consumer_detected_at_start = None
        trial_rows: list[dict] = []
        try:
            consumer_detected_at_start = self._auto_wait_for_lsl_consumer()
            self.log_event(event_name=self._event("experiment.start"), extra_metadata={"task": self.task_name})
            self.log_event(
                event_name=self._event("sequence.start"),
                extra_metadata={
                    "task": self.task_name,
                    "start_code": self.task_config.start_code,
                    "end_code": self.task_config.end_code,
                    "interval_s": self.task_config.interval_s,
                },
            )

            total_codes = len(self._sequence)
            for sequence_index, raw_code in enumerate(self._sequence, start=1):
                send_time, marker_result, marker_message = self._send_raw_test_marker(
                    raw_code=raw_code,
                    sequence_index=sequence_index,
                    total_codes=total_codes,
                )

                trial_row = {
                    "participant": self.participant,
                    "session": self.session,
                    "task": self.task_name,
                    "block": 1,
                    "trial_index": sequence_index,
                    "condition": f"code_{raw_code:03d}",
                    "stimulus_parameters": {
                        "raw_marker_code": raw_code,
                        "interval_s": self.task_config.interval_s,
                    },
                    "response": None,
                    "rt": None,
                    "correct": None,
                    "feedback": None,
                    "timeout": False,
                    "fixation_onset": None,
                    "stim_onset": send_time,
                    "response_time_abs": None,
                    "feedback_onset": None,
                    "iti_onset": send_time,
                    "trial_end": send_time + self.task_config.interval_s,
                    "lsl_marker_codes": [raw_code if marker_result.lsl_sent else -1],
                    "lpt_marker_codes": [raw_code if marker_result.lpt_sent else -1],
                    "event_keys": [self._event("pulse")],
                    "fnirs_marker_codes": [marker_result.payload["fnirs_code"]] if marker_result.fnirs_sent and "fnirs_code" in marker_result.payload else [],
                    "task_specific_data": {
                        "raw_marker_code": raw_code,
                        "sequence_index": sequence_index,
                        "send_interval_s": self.task_config.interval_s,
                        "marker_label": marker_result.label,
                    },
                }
                self.log_trial_row(trial_row)
                summary_row = dict(trial_row)
                summary_row.update(trial_row["task_specific_data"])
                trial_rows.append(summary_row)

                deadline = send_time + self.task_config.interval_s
                while self.global_clock.getTime() < deadline:
                    self.check_escape()
                    self._status_text(marker_message)
                    self.window.flip()

            self.log_event(event_name=self._event("sequence.end"), extra_metadata={"task": self.task_name, "n_markers": len(self._sequence)})
            self.log_event(event_name=self._event("experiment.end"), extra_metadata={"task": self.task_name})
            self.run_summary = {
                "n_trials": len(trial_rows),
                "timeout_rate": 0.0,
                "first_marker_code": self._sequence[0],
                "last_marker_code": self._sequence[-1],
                "interval_s": self.task_config.interval_s,
                "consumer_detected_at_start": consumer_detected_at_start,
                "lsl_markers_sent": sum(1 for row in trial_rows if row["lsl_marker_codes"][0] != -1),
                "lpt_markers_sent": sum(1 for row in trial_rows if row["lpt_marker_codes"][0] != -1),
                "task_positioning": "transport-only marker sweep task for validating raw 1-255 marker delivery over LSL and LPT",
            }
            self.final_status = "completed"
            if self.task_config.completion_hold_s > 0:
                self.show_message(
                    "Marker Test 已完成。\n\n"
                    f"已顺序发送 {len(self._sequence)} 个测试 marker。",
                    wait_for_key=False,
                )
                core.wait(self.task_config.completion_hold_s)
        except SafeExitRequested:
            self.final_status = "safe_exit"
            self.log_event(event_name="system.safe_exit.requested")
        finally:
            self.finalize()


__all__ = ["MarkerTestTask"]