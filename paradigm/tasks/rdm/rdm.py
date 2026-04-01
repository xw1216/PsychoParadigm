from pathlib import Path

from paradigm.config import AppConfig
from paradigm.hardware.eyetracking import AOIRegion
from paradigm.runtime.base_experiment import BaseExperiment, SafeExitRequested
from paradigm.tasks.rdm.rdm_logic import RDMTrial, build_rdm_trials, determine_rdm_trial_quality, export_ddm_ready_table, export_psychometric_summary, resolve_rdm_feedback_plan


class RDMTask(BaseExperiment):
    def __init__(self, participant: str, session: str, config: AppConfig | None = None) -> None:
        from psychopy import visual

        super().__init__(task_name="rdm", participant=participant, session=session, config=config)
        self.task_config = self.config.rdm
        self.dot_stim = visual.DotStim(
            win=self.window,
            nDots=self.task_config.n_dots,
            fieldSize=self.task_config.field_size,
            dotLife=self.task_config.dot_life,
            speed=self.task_config.speed,
            signalDots=self.task_config.signal_dots,
            noiseDots=self.task_config.noise_dots,
            dotSize=self.task_config.dot_size,
        )
        self.feedback_text = visual.TextStim(self.window, text="", height=0.05, color="white", pos=(0, -0.25))
        self.motion_aoi = [AOIRegion(name="motion_field", left=-0.35, right=0.35, bottom=-0.35, top=0.35)]
        self._trials = build_rdm_trials(self.task_config, self.rng)

    def _draw_motion(self) -> None:
        self.dot_stim.draw()
        self.fixation.draw()

    def _draw_feedback(self) -> None:
        self.feedback_text.draw()

    @staticmethod
    def _event(name: str) -> str:
        return f"rdm.{name}"

    @staticmethod
    def export_psychometric_summary(trial_rows: list[dict], output_path: Path) -> None:
        export_psychometric_summary(trial_rows, output_path)

    @staticmethod
    def export_ddm_ready_table(trial_rows: list[dict], output_path: Path) -> None:
        export_ddm_ready_table(trial_rows, output_path)

    def run(self) -> None:
        total_trials = len(self._trials)
        mode_prefix = "练习模式：" if self.config.practice.enabled else ""
        try:
            self.show_labrecorder_wait_screen()
            self.experiment_clock.reset()
            self.send_marker_now(event_name=self._event("experiment.start"), metadata={"task": self.task_name})
            self.show_message(
                f"{mode_prefix}随机点运动任务\n\n请判断整体运动方向，并使用左右方向键作答。\n请尽量又快又准。\n当前版本每个试次后都会给出正误反馈。\n\n按 {self.continue_key_label()} 开始。"
            )

            current_block = None
            trial_rows: list[dict] = []
            for trial in self._trials:
                fixation_event = self._event("fixation.onset")
                motion_event = self._event("motion.onset")
                timeout_event = self._event("response.timeout")
                response_left_event = self._event("response.left")
                response_right_event = self._event("response.right")
                feedback_correct_event = self._event("feedback.correct")
                feedback_incorrect_event = self._event("feedback.incorrect")
                iti_event = self._event("iti.onset")
                if trial.block != current_block:
                    current_block = trial.block
                    self.send_marker_now(event_name=self._event("block.start"), metadata={"task": self.task_name, "block": current_block}, block=current_block, trial=trial.trial_index)

                fixation_onset = self.fixation_period(duration_s=self.task_config.fixation_s, event_name=fixation_event, block=trial.block, trial=trial.trial_index)
                self.dot_stim.coherence = trial.coherence
                self.dot_stim.dir = 180 if trial.direction == "left" else 0
                response_data = self.wait_for_response(
                    draw_fn=self._draw_motion,
                    valid_keys=self.task_config.response_keys,
                    timeout_s=self.task_config.response_timeout_s,
                    onset_event_code=None,
                    onset_label=None,
                    onset_event_name=motion_event,
                    block=trial.block,
                    trial=trial.trial_index,
                    metadata={"task": self.task_name, "block": trial.block, "trial": trial.trial_index, "direction": trial.direction, "coherence": trial.coherence},
                )
                self.poll_and_log_aoi(aoi_regions=self.motion_aoi, block=trial.block, trial=trial.trial_index)
                response = response_data["response"]
                timeout = response_data["timeout"]
                correct = response == trial.direction if response is not None else False
                lsl_codes: list[int] = [self.task_config.marker_codes[motion_event]]
                lpt_codes: list[int] = [self.task_config.marker_codes[motion_event]]
                event_keys: list[str] = [motion_event]
                fnirs_codes: list[int] = []
                motion_fnirs = self.fnirs_code_for(self.task_config.marker_codes[motion_event])
                if motion_fnirs is not None:
                    fnirs_codes.append(motion_fnirs)
                fixation_break_detected = False
                invalid_response = False
                response_locked_rt = response_data["rt"]
                cpp_slope_proxy = (trial.coherence / response_data["rt"]) if response_data["rt"] not in (None, 0) else None

                if timeout:
                    timeout_marker = self.send_marker_now(event_name=timeout_event, metadata={"task": self.task_name, "block": trial.block, "trial": trial.trial_index}, block=trial.block, trial=trial.trial_index)
                    lsl_codes.append(timeout_marker.code if timeout_marker.lsl_sent else -1)
                    lpt_codes.append(timeout_marker.code if timeout_marker.lpt_sent else -1)
                    event_keys.append(timeout_marker.label or timeout_event)
                    if timeout_marker.fnirs_sent:
                        fnirs_codes.append(timeout_marker.payload.get("fnirs_code", -1))
                    response_event = timeout_event
                else:
                    response_event_name = response_left_event if response == "left" else response_right_event
                    response_marker = self.send_marker_now(event_name=response_event_name, metadata={"task": self.task_name, "block": trial.block, "trial": trial.trial_index, "rt": response_data["rt"]}, block=trial.block, trial=trial.trial_index)
                    lsl_codes.append(response_marker.code if response_marker.lsl_sent else -1)
                    lpt_codes.append(response_marker.code if response_marker.lpt_sent else -1)
                    event_keys.append(response_marker.label or response_event_name)
                    if response_marker.fnirs_sent:
                        fnirs_codes.append(response_marker.payload.get("fnirs_code", -1))
                    response_event = response_marker.label or response_event_name

                feedback_label, feedback_event_suffix, feedback_text = resolve_rdm_feedback_plan(correct=correct, timeout=timeout, feedback_mode=self.task_config.feedback_mode)
                feedback_event_name = self._event(feedback_event_suffix) if feedback_event_suffix else None
                if feedback_event_name is not None:
                    feedback_code = self.task_config.marker_codes[feedback_event_name]
                    self.feedback_text.text = feedback_text or ""
                    if feedback_label == "correct":
                        self.feedback_text.color = "lightgreen"
                    elif feedback_label == "incorrect":
                        self.feedback_text.color = "tomato"
                    else:
                        self.feedback_text.color = "gold"
                    feedback_onset = self.present_timed_event(
                        draw_fn=self._draw_feedback,
                        duration_s=self.task_config.feedback_s,
                        event_code=None,
                        label=None,
                        event_name=feedback_event_name,
                        block=trial.block,
                        trial=trial.trial_index,
                        metadata={"task": self.task_name, "block": trial.block, "trial": trial.trial_index, "correct": correct, "direction": trial.direction, "coherence": trial.coherence, "feedback_mode": self.task_config.feedback_mode},
                    )
                    lsl_codes.append(feedback_code)
                    lpt_codes.append(feedback_code)
                    event_keys.append(feedback_event_name)
                    feedback_fnirs = self.fnirs_code_for(feedback_code)
                    if feedback_fnirs is not None:
                        fnirs_codes.append(feedback_fnirs)
                else:
                    feedback_onset = None

                exclude_trial, exclude_reason = determine_rdm_trial_quality(
                    timeout=timeout,
                    fixation_break_detected=fixation_break_detected,
                    invalid_response=invalid_response,
                    exclude_timeouts_from_analysis=self.task_config.exclude_timeouts_from_analysis,
                )

                self.present_interval(lambda: None, duration_s=self.task_config.post_response_blank_s)
                iti_duration = self.sample_iti(self.task_config.iti_range_s)
                iti_onset = self.present_timed_event(draw_fn=self.fixation.draw, duration_s=iti_duration, event_code=None, label=None, event_name=iti_event, block=trial.block, trial=trial.trial_index, metadata={"task": self.task_name, "block": trial.block, "trial": trial.trial_index, "iti_s": iti_duration})
                lsl_codes.append(self.task_config.marker_codes[iti_event])
                lpt_codes.append(self.task_config.marker_codes[iti_event])
                event_keys.append(iti_event)
                iti_fnirs = self.fnirs_code_for(self.task_config.marker_codes[iti_event])
                if iti_fnirs is not None:
                    fnirs_codes.append(iti_fnirs)


                trial_row = {
                        "participant": self.participant,
                        "session": self.session,
                        "task": self.task_name,
                        "block": trial.block,
                        "trial_index": trial.trial_index,
                        "condition": f"{trial.direction}_{trial.coherence}",
                        "stimulus_parameters": {"direction": trial.direction, "coherence": trial.coherence, "nDots": self.task_config.n_dots, "fieldSize": self.task_config.field_size, "dotLife": self.task_config.dot_life, "speed": self.task_config.speed, "signalDots": self.task_config.signal_dots, "noiseDots": self.task_config.noise_dots},
                        "response": response,
                        "rt": response_data["rt"],
                        "correct": correct,
                        "feedback": feedback_label,
                        "timeout": timeout,
                        "fixation_onset": fixation_onset,
                        "stim_onset": response_data["onset_flip"],
                        "response_time_abs": response_data["response_abs"],
                        "feedback_onset": feedback_onset,
                        "iti_onset": iti_onset,
                        "trial_end": iti_onset + iti_duration,
                        "lsl_marker_codes": lsl_codes,
                        "lpt_marker_codes": lpt_codes,
                        "event_keys": event_keys,
                        "fnirs_marker_codes": fnirs_codes,
                        "task_specific_data": {
                            "direction": trial.direction,
                            "coherence": trial.coherence,
                            "response_event": response_event,
                            "feedback_event": feedback_event_name,
                            "feedback_mode": self.task_config.feedback_mode,
                            "response_locked_rt": response_locked_rt,
                            "cpp_slope_proxy": cpp_slope_proxy,
                            "fixation_break_detected": fixation_break_detected,
                            "fixation_break_online_detection": self.task_config.online_fixation_break_detection,
                            "exclude_trial": exclude_trial,
                            "exclude_reason": exclude_reason,
                            "invalid_response": invalid_response,
                            "confidence_rating_enabled": self.task_config.confidence_rating_enabled,
                        },
                    }
                self.log_trial_row(trial_row)
                analysis_row = dict(trial_row)
                analysis_row.update(trial_row["task_specific_data"])
                trial_rows.append(analysis_row)

                if trial.trial_index < total_trials and trial.trial_index % self.config.common.break_every_n_trials == 0:
                    self.show_break(block=trial.block, completed_trials=trial.trial_index, total_trials=total_trials)

                next_trial = next((item for item in self._trials if item.trial_index == trial.trial_index + 1), None)
                if next_trial is None or next_trial.block != trial.block:
                    self.send_marker_now(event_name=self._event("block.end"), metadata={"task": self.task_name, "block": trial.block}, block=trial.block, trial=trial.trial_index)

            self.send_marker_now(event_name=self._event("experiment.end"), metadata={"task": self.task_name})
            coherence_levels = sorted({row["coherence"] for row in trial_rows})
            accuracy_by_coherence = {
                str(level): (sum(1 for row in trial_rows if row["coherence"] == level and row["correct"]) / max(1, sum(1 for row in trial_rows if row["coherence"] == level)))
                for level in coherence_levels
            }
            mean_rt_by_coherence = {
                str(level): (
                    sum(float(row["rt"]) for row in trial_rows if row["coherence"] == level and row.get("rt") not in (None, ""))
                    / max(1, sum(1 for row in trial_rows if row["coherence"] == level and row.get("rt") not in (None, "")))
                )
                for level in coherence_levels
            }
            self.run_summary = {
                "n_trials": len(trial_rows),
                "timeout_rate": (sum(1 for row in trial_rows if row["timeout"]) / len(trial_rows)) if trial_rows else None,
                "feedback_mode": self.task_config.feedback_mode,
                "accuracy_by_coherence": accuracy_by_coherence,
                "mean_rt_by_coherence": mean_rt_by_coherence,
                "analysis_positioning": "rapid evidence-accumulation validation for coherence-accuracy/RT, CPP, response-locked dynamics, and sensorimotor beta",
                "practice_staircase_enabled": self.task_config.practice_staircase_enabled,
            }
            self.final_status = "completed"
            self.export_psychometric_summary(trial_rows, self.paths.run_dir / "rdm_psychometric_summary.csv")
            self.export_ddm_ready_table(trial_rows, self.paths.run_dir / "rdm_ddm_ready.csv")
            self.show_message(f"{mode_prefix}RDM 任务已完成。\n\n按 {self.continue_key_label()} 结束。")
        except SafeExitRequested:
            self.final_status = "safe_exit"
            self.log_event(event_name="system.safe_exit.requested")
        finally:
            self.finalize()


__all__ = [
    "RDMTask",
    "RDMTrial",
    "build_rdm_trials",
    "determine_rdm_trial_quality",
    "resolve_rdm_feedback_plan",
]
