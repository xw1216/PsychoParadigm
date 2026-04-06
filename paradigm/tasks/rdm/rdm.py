from paradigm.config import AppConfig
from paradigm.analysis.rdm import summarize_rdm_run
from paradigm.hardware.eyetracking import AOIRegion
from paradigm.runtime.base_experiment import BaseExperiment, SafeExitRequested
from paradigm.tasks.rdm.rdm_logic import RDMTrial, build_rdm_trials, determine_rdm_trial_quality, resolve_rdm_feedback_plan


class RDMTask(BaseExperiment):
    def __init__(self, participant: str, session: str, config: AppConfig | None = None) -> None:
        from psychopy import visual

        super().__init__(task_name="rdm", participant=participant, session=session, config=config)
        self.task_config = self.config.rdm
        self.dot_stim = visual.DotStim(
            win=self.window,
            nDots=self.task_config.n_dots,
            fieldSize=self.task_config.field_size,
            fieldShape=self.task_config.field_shape,
            dotLife=self.task_config.dot_life,
            speed=self.task_config.speed,
            signalDots=self.task_config.signal_dots,
            noiseDots=self.task_config.noise_dots,
            dotSize=self.task_config.dot_size,
        )
        self.feedback_text = visual.TextStim(self.window, text="", height=0.05, color="white", pos=(0, -0.25), font=self.text_font)
        self.motion_aoi = [AOIRegion(name="motion_field", left=-0.35, right=0.35, bottom=-0.35, top=0.35)]
        self._trials = build_rdm_trials(self.task_config, self.rng)

    def _draw_motion(self) -> None:
        self.dot_stim.draw()
        self.fixation.draw()

    def _draw_premotion(self) -> None:
        self.dot_stim.draw()
        self.fixation.draw()

    def _draw_feedback(self) -> None:
        self.feedback_text.draw()

    @staticmethod
    def _event(name: str) -> str:
        return f"rdm.{name}"

    def run(self) -> None:
        total_trials = len(self._trials)
        mode_prefix = "练习模式：" if self.config.practice.enabled else ""
        try:
            self.show_labrecorder_wait_screen()
            self.experiment_clock.reset()
            self.send_marker_now(event_name=self._event("experiment.start"), metadata={"task": self.task_name})
            self.show_message(
                f"{mode_prefix}随机点运动任务\n\n每个试次先出现短暂的 0% coherence 预阶段，再进入真正的 coherent motion。\n请判断整体主运动方向，并尽量又快又准地按左右方向键作答。"
                + (
                    "\n\n当前练习模式只使用较高 coherence 档位（0.4 / 0.6 / 0.8），帮助你先熟悉方向感。"
                    if self.config.practice.enabled
                    else "\n\n正式模式包含从较难到较易的多个 coherence 档位。"
                )
                + f"\n\n按 {self.continue_key_label()} 开始。"
            )

            current_block = None
            trial_rows: list[dict] = []
            for trial in self._trials:
                fixation_event = self._event("fixation.onset")
                premotion_event = self._event("premotion.onset")
                motion_event = self._event("motion.onset")
                timeout_event = self._event("response.timeout")
                response_left_event = self._event("response.left")
                response_right_event = self._event("response.right")
                feedback_correct_event = self._event("feedback.correct")
                feedback_error_event = self._event("feedback.error")
                post_response_blank_event = self._event("post_response_blank.onset")
                iti_event = self._event("iti.onset")
                if trial.block != current_block:
                    current_block = trial.block
                    self.send_marker_now(event_name=self._event("block.start"), metadata={"task": self.task_name, "block": current_block}, block=current_block, trial=trial.trial_index)

                fixation_onset = self.fixation_period(duration_s=self.task_config.fixation_s, event_name=fixation_event, block=trial.block, trial=trial.trial_index)
                self.dot_stim.coherence = 0.0
                premotion_onset, premotion_marker = self.present_timed_event(
                    draw_fn=self._draw_premotion,
                    duration_s=self.task_config.premotion_s,
                    event_code=None,
                    label=None,
                    event_name=premotion_event,
                    block=trial.block,
                    trial=trial.trial_index,
                    metadata={"task": self.task_name, "block": trial.block, "trial": trial.trial_index, "signed_coherence": trial.signed_coherence},
                )
                self.dot_stim.coherence = trial.coherence
                self.dot_stim.dir = 180 if trial.direction == "left" else 0
                response_data = self.wait_for_response(
                    draw_fn=self._draw_motion,
                    valid_keys=self.task_config.response_keys,
                    timeout_s=self.task_config.coherent_motion_max_s,
                    onset_event_code=None,
                    onset_label=None,
                    onset_event_name=motion_event,
                    block=trial.block,
                    trial=trial.trial_index,
                    metadata={"task": self.task_name, "block": trial.block, "trial": trial.trial_index, "direction": trial.direction, "coherence": trial.coherence, "signed_coherence": trial.signed_coherence},
                )
                self.poll_and_log_aoi(aoi_regions=self.motion_aoi, block=trial.block, trial=trial.trial_index)
                response = response_data["response"]
                timeout = response_data["timeout"]
                correct = response == trial.direction if response is not None else False
                lsl_codes: list[int] = []
                lpt_codes: list[int] = []
                event_keys: list[str] = [premotion_event, motion_event]
                fnirs_codes: list[int] = []
                self.append_marker_result_codes(premotion_marker, lsl_codes=lsl_codes, lpt_codes=lpt_codes, fnirs_codes=fnirs_codes)
                self.append_marker_result_codes(response_data["onset_marker"], lsl_codes=lsl_codes, lpt_codes=lpt_codes, fnirs_codes=fnirs_codes)
                fixation_break_detected = False
                invalid_response = False
                response_locked_rt = response_data["rt"]
                cpp_slope_proxy = (trial.coherence / response_data["rt"]) if response_data["rt"] not in (None, 0) else None

                if timeout:
                    timeout_marker = self.send_marker_now(event_name=timeout_event, metadata={"task": self.task_name, "block": trial.block, "trial": trial.trial_index}, block=trial.block, trial=trial.trial_index)
                    event_keys.append(timeout_marker.label or timeout_event)
                    self.append_marker_result_codes(timeout_marker, lsl_codes=lsl_codes, lpt_codes=lpt_codes, fnirs_codes=fnirs_codes)
                    response_event = timeout_event
                else:
                    response_event_name = response_left_event if response == "left" else response_right_event
                    response_marker = self.send_marker_now(event_name=response_event_name, metadata={"task": self.task_name, "block": trial.block, "trial": trial.trial_index, "rt": response_data["rt"]}, block=trial.block, trial=trial.trial_index)
                    event_keys.append(response_marker.label or response_event_name)
                    self.append_marker_result_codes(response_marker, lsl_codes=lsl_codes, lpt_codes=lpt_codes, fnirs_codes=fnirs_codes)
                    response_event = response_marker.label or response_event_name

                feedback_label, feedback_event_suffix, feedback_text = resolve_rdm_feedback_plan(correct=correct, timeout=timeout, feedback_mode=self.task_config.feedback_mode)
                feedback_event_name = self._event(feedback_event_suffix) if feedback_event_suffix else None
                if feedback_event_name is not None:
                    feedback_code = self.task_config.marker_codes[feedback_event_name]
                    self.feedback_text.text = feedback_text or ""
                    if feedback_label == "correct":
                        self.feedback_text.color = "lightgreen"
                    elif feedback_label == "error":
                        self.feedback_text.color = "tomato"
                    else:
                        self.feedback_text.color = "gold"
                    feedback_onset, feedback_marker = self.present_timed_event(
                        draw_fn=self._draw_feedback,
                        duration_s=self.task_config.feedback_s,
                        event_code=None,
                        label=None,
                        event_name=feedback_event_name,
                        block=trial.block,
                        trial=trial.trial_index,
                        metadata={"task": self.task_name, "block": trial.block, "trial": trial.trial_index, "correct": correct, "direction": trial.direction, "coherence": trial.coherence, "feedback_mode": self.task_config.feedback_mode},
                    )
                    event_keys.append(feedback_event_name)
                    self.append_marker_result_codes(feedback_marker, lsl_codes=lsl_codes, lpt_codes=lpt_codes, fnirs_codes=fnirs_codes)
                else:
                    feedback_onset = None

                exclude_trial, exclude_reason = determine_rdm_trial_quality(
                    timeout=timeout,
                    fixation_break_detected=fixation_break_detected,
                    invalid_response=invalid_response,
                    exclude_timeouts_from_analysis=self.task_config.exclude_timeouts_from_analysis,
                )

                post_response_blank_onset, post_response_blank_marker = self.present_timed_event(
                    draw_fn=lambda: None,
                    duration_s=self.task_config.post_response_blank_s,
                    event_code=None,
                    label=None,
                    event_name=post_response_blank_event,
                    block=trial.block,
                    trial=trial.trial_index,
                    metadata={"task": self.task_name, "block": trial.block, "trial": trial.trial_index},
                )
                event_keys.append(post_response_blank_event)
                self.append_marker_result_codes(post_response_blank_marker, lsl_codes=lsl_codes, lpt_codes=lpt_codes, fnirs_codes=fnirs_codes)
                iti_duration = self.sample_iti(self.task_config.iti_range_s)
                iti_onset, iti_marker = self.present_timed_event(draw_fn=self.fixation.draw, duration_s=iti_duration, event_code=None, label=None, event_name=iti_event, block=trial.block, trial=trial.trial_index, metadata={"task": self.task_name, "block": trial.block, "trial": trial.trial_index, "iti_s": iti_duration})
                event_keys.append(iti_event)
                self.append_marker_result_codes(iti_marker, lsl_codes=lsl_codes, lpt_codes=lpt_codes, fnirs_codes=fnirs_codes)


                trial_row = {
                        "participant": self.participant,
                        "session": self.session,
                        "task": self.task_name,
                        "block": trial.block,
                        "trial_index": trial.trial_index,
                        "condition": f"{trial.signed_coherence:+.2f}",
                        "stimulus_parameters": {
                            "direction": trial.direction,
                            "signed_coherence": trial.signed_coherence,
                            "absolute_coherence": trial.coherence,
                            "premotion_s": self.task_config.premotion_s,
                            "coherent_motion_max_s": self.task_config.coherent_motion_max_s,
                            "nDots": self.task_config.n_dots,
                            "fieldSize": self.task_config.field_size,
                            "fieldShape": self.task_config.field_shape,
                            "dotLife": self.task_config.dot_life,
                            "speed": self.task_config.speed,
                            "signalDots": self.task_config.signal_dots,
                            "noiseDots": self.task_config.noise_dots,
                            "dotSize": self.task_config.dot_size,
                            "frame_rate_hz": self.frame_rate_estimate or self.config.screen.target_frame_rate,
                        },
                        "response": response,
                        "rt": response_data["rt"],
                        "correct": correct,
                        "feedback": feedback_label,
                        "timeout": timeout,
                        "fixation_onset": fixation_onset,
                        "stim_onset": response_data["onset_time"],
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
                            "signed_coherence": trial.signed_coherence,
                            "absolute_coherence": trial.coherence,
                            "premotion_onset": premotion_onset,
                            "response_event": response_event,
                            "feedback_event": feedback_event_name,
                            "post_response_blank_onset": post_response_blank_onset,
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
                summary_row = dict(trial_row)
                summary_row.update(trial_row["task_specific_data"])
                trial_rows.append(summary_row)

                if trial.trial_index < total_trials and trial.trial_index % self.config.common.break_every_n_trials == 0:
                    self.show_break(block=trial.block, completed_trials=trial.trial_index, total_trials=total_trials)

                next_trial = next((item for item in self._trials if item.trial_index == trial.trial_index + 1), None)
                if next_trial is None or next_trial.block != trial.block:
                    self.send_marker_now(event_name=self._event("block.end"), metadata={"task": self.task_name, "block": trial.block}, block=trial.block, trial=trial.trial_index)

            self.send_marker_now(event_name=self._event("experiment.end"), metadata={"task": self.task_name})
            self.run_summary = summarize_rdm_run(trial_rows, fast_rt_threshold_s=self.task_config.fast_response_threshold_s)
            self.run_summary["feedback_mode"] = self.task_config.feedback_mode
            self.run_summary["analysis_positioning"] = "perceptual decision task for psychometric/chronometric curves, CPP, and DDM-style evidence accumulation"
            self.run_summary["practice_staircase_enabled"] = self.task_config.practice_staircase_enabled
            self.run_summary["premotion_s"] = self.task_config.premotion_s
            self.final_status = "completed"
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
