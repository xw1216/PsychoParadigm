from paradigm.config import AppConfig
from paradigm.hardware.eyetracking import AOIRegion
from paradigm.runtime.base_experiment import BaseExperiment, SafeExitRequested
from paradigm.runtime.choice_panels import ChoicePanelPair
from paradigm.analysis.doors import summarize_doors_run
from paradigm.tasks.doors.doors_logic import DoorTrial, build_doors_trials, format_doors_feedback


class DoorsTask(BaseExperiment):
    def __init__(self, participant: str, session: str, config: AppConfig | None = None) -> None:
        from psychopy import visual

        super().__init__(task_name="doors", participant=participant, session=session, config=config)
        self.task_config = self.config.doors
        self.choice_panels = ChoicePanelPair(visual, self.window, left_label="←", right_label="→", text_font=self.text_font)
        self.feedback_text = visual.TextStim(self.window, text="", height=0.08, color="white", font=self.text_font)
        self.choice_aois = self.choice_panels.build_aois(left_name="left_door", right_name="right_door")
        self._trials = build_doors_trials(self.task_config, self.rng)

    def _draw_choice_screen(self, selected: str | None = None) -> None:
        self.choice_panels.draw(selected=selected)

    def _draw_feedback(self) -> None:
        self.feedback_text.draw()

    @staticmethod
    def _event(name: str) -> str:
        return f"doors.{name}"

    def run(self) -> None:
        total_trials = len(self._trials)
        mode_prefix = "练习模式：" if self.config.practice.enabled else ""
        trial_rows: list[dict] = []
        previous_feedback = None
        current_feedback_streak_label = None
        current_feedback_streak_length = 0
        try:
            self.show_labrecorder_wait_screen()
            self.experiment_clock.reset()
            self.send_marker_now(event_name=self._event("experiment.start"), metadata={"task": self.task_name})
            self.show_message(
                f"{mode_prefix}Doors 任务\n\n请使用左右方向键选择左门或右门。\n每次选择后都会呈现反馈。\n\n按 {self.continue_key_label()} 开始。"
            )

            for block in range(1, self.task_config.blocks + 1):
                self.send_marker_now(event_name=self._event("block.start"), metadata={"task": self.task_name, "block": block}, block=block)
                block_trials = [trial for trial in self._trials if trial.block == block]
                for trial in block_trials:
                    trial_in_block = trial.trial_index - (block - 1) * self.task_config.trials_per_block
                    fixation_event = self._event("fixation.onset")
                    choice_event = self._event("choice.onset")
                    timeout_event = self._event("response.timeout")
                    response_left_event = self._event("response.left")
                    response_right_event = self._event("response.right")
                    post_choice_event = self._event("post_choice_delay.onset")
                    feedback_gain_event = self._event("feedback.gain")
                    feedback_loss_event = self._event("feedback.loss")
                    feedback_timeout_event = self._event("feedback.timeout")
                    iti_event = self._event("iti.onset")

                    fixation_onset = self.fixation_period(duration_s=self.task_config.fixation_s, event_name=fixation_event, block=block, trial=trial.trial_index)
                    response_data = self.wait_for_response(
                        draw_fn=self._draw_choice_screen,
                        valid_keys=self.task_config.response_keys,
                        timeout_s=self.task_config.response_timeout_s,
                        onset_event_code=None,
                        onset_label=None,
                        onset_event_name=choice_event,
                        block=block,
                        trial=trial.trial_index,
                        metadata={"task": self.task_name, "block": block, "trial": trial.trial_index},
                    )
                    self.poll_and_log_aoi(aoi_regions=self.choice_aois, block=block, trial=trial.trial_index)

                    lsl_codes: list[int] = []
                    lpt_codes: list[int] = []
                    event_keys: list[str] = [choice_event]
                    fnirs_codes: list[int] = []
                    self.append_marker_result_codes(response_data["onset_marker"], lsl_codes=lsl_codes, lpt_codes=lpt_codes, fnirs_codes=fnirs_codes)
                    response_label = response_data["response"]
                    timeout = response_data["timeout"]

                    if timeout:
                        timeout_marker = self.send_marker_now(event_name=timeout_event, metadata={"task": self.task_name, "block": block, "trial": trial.trial_index}, block=block, trial=trial.trial_index)
                        event_keys.append(timeout_marker.label or timeout_event)
                        self.append_marker_result_codes(timeout_marker, lsl_codes=lsl_codes, lpt_codes=lpt_codes, fnirs_codes=fnirs_codes)
                        response_event = timeout_event
                        feedback_event_name = feedback_timeout_event
                        feedback_code = self.task_config.marker_codes[feedback_event_name]
                        feedback_text = self.task_config.timeout_feedback_text
                        feedback_color = "gold"
                        feedback_value = None
                        displayed_feedback = "timeout"
                        feedback_semantics = "timeout_miss"
                    else:
                        response_event_name = response_left_event if response_label == "left" else response_right_event
                        response_marker = self.send_marker_now(
                            event_name=response_event_name,
                            metadata={"task": self.task_name, "block": block, "trial": trial.trial_index, "response": response_label, "rt": response_data["rt"]},
                            block=block,
                            trial=trial.trial_index,
                        )
                        event_keys.append(response_marker.label or response_event_name)
                        self.append_marker_result_codes(response_marker, lsl_codes=lsl_codes, lpt_codes=lpt_codes, fnirs_codes=fnirs_codes)
                        response_event = response_marker.label or response_event_name
                        feedback_event_name = feedback_gain_event if trial.feedback_type == "gain" else feedback_loss_event
                        feedback_code = self.task_config.marker_codes[feedback_event_name]
                        feedback_text, feedback_color, feedback_value = format_doors_feedback(trial, self.task_config)
                        displayed_feedback = trial.feedback_type
                        feedback_semantics = "outcome"

                    post_choice_delay_onset, post_choice_delay_marker = self.present_timed_event(
                        draw_fn=lambda: self._draw_choice_screen(selected=response_label),
                        duration_s=self.task_config.post_choice_delay_s,
                        event_code=None,
                        label=None,
                        event_name=post_choice_event,
                        block=block,
                        trial=trial.trial_index,
                        metadata={"task": self.task_name, "block": block, "trial": trial.trial_index},
                    )
                    event_keys.append(post_choice_event)
                    self.append_marker_result_codes(post_choice_delay_marker, lsl_codes=lsl_codes, lpt_codes=lpt_codes, fnirs_codes=fnirs_codes)

                    self.feedback_text.text = feedback_text
                    self.feedback_text.color = feedback_color
                    feedback_onset, feedback_marker = self.present_timed_event(
                        draw_fn=self._draw_feedback,
                        duration_s=self.task_config.feedback_s,
                        event_code=None,
                        label=None,
                        event_name=feedback_event_name,
                        block=block,
                        trial=trial.trial_index,
                        metadata={"task": self.task_name, "block": block, "trial": trial.trial_index, "feedback_type": trial.feedback_type, "feedback_value": feedback_value},
                    )
                    event_keys.append(feedback_event_name)
                    self.append_marker_result_codes(feedback_marker, lsl_codes=lsl_codes, lpt_codes=lpt_codes, fnirs_codes=fnirs_codes)

                    iti_duration = self.sample_iti(self.task_config.iti_range_s)
                    iti_onset, iti_marker = self.present_timed_event(draw_fn=self.fixation.draw, duration_s=iti_duration, event_code=None, label=None, event_name=iti_event, block=block, trial=trial.trial_index, metadata={"task": self.task_name, "block": block, "trial": trial.trial_index, "iti_s": iti_duration})
                    event_keys.append(iti_event)
                    self.append_marker_result_codes(iti_marker, lsl_codes=lsl_codes, lpt_codes=lpt_codes, fnirs_codes=fnirs_codes)

                    exclude_trial = timeout
                    exclude_reason = "timeout" if timeout else None
                    invalid_response = timeout
                    current_feedback_streak_length = current_feedback_streak_length + 1 if displayed_feedback == current_feedback_streak_label else 1
                    current_feedback_streak_label = displayed_feedback

                    trial_row = {
                            "participant": self.participant,
                            "session": self.session,
                            "task": self.task_name,
                            "block": block,
                            "trial_index": trial.trial_index,
                            "condition": trial.feedback_type,
                            "stimulus_parameters": {"door_positions": {"left": -0.25, "right": 0.25}, "post_choice_delay_s": self.task_config.post_choice_delay_s},
                            "response": response_label,
                            "rt": response_data["rt"],
                            "correct": None,
                            "feedback": displayed_feedback,
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
                                "post_choice_delay_onset": post_choice_delay_onset,
                                "scheduled_feedback_type": trial.feedback_type,
                                "feedback_type": displayed_feedback,
                                "feedback_semantics": feedback_semantics,
                                "feedback_value": feedback_value,
                                "feedback_display_mode": self.task_config.feedback_display_mode,
                                "response_event": response_event,
                                "feedback_event": feedback_event_name,
                                "previous_feedback": previous_feedback,
                                "feedback_run_length": current_feedback_streak_length,
                                "block_trial_index": trial_in_block,
                                "exclude_trial": exclude_trial,
                                "exclude_reason": exclude_reason,
                                "invalid_response": invalid_response,
                            },
                        }
                    self.log_trial_row(trial_row)
                    summary_row = dict(trial_row)
                    summary_row.update(trial_row["task_specific_data"])
                    trial_rows.append(summary_row)
                    previous_feedback = displayed_feedback

                    if trial_in_block < self.task_config.trials_per_block and trial_in_block % self.config.common.break_every_n_trials == 0:
                        self.show_break(block=block, completed_trials=trial.trial_index, total_trials=total_trials)

                self.send_marker_now(event_name=self._event("block.end"), metadata={"task": self.task_name, "block": block}, block=block)

            self.send_marker_now(event_name=self._event("experiment.end"), metadata={"task": self.task_name})
            feedback_event_complete = all(any(name.startswith("doors.feedback.") for name in row["event_keys"]) for row in trial_rows)
            self.run_summary = summarize_doors_run(trial_rows, fast_rt_threshold_s=self.task_config.fast_response_threshold_s)
            self.run_summary["feedback_event_complete"] = feedback_event_complete
            self.run_summary["task_positioning"] = "feedback-locked validation task for RewP/FRN and feedback P3, not an RL updating task"
            self.final_status = "completed"
            self.show_message(f"{mode_prefix}Doors 任务已完成。\n\n按 {self.continue_key_label()} 结束。")
        except SafeExitRequested:
            self.final_status = "safe_exit"
            self.log_event(event_name="system.safe_exit.requested")
        finally:
            self.finalize()


__all__ = ["DoorTrial", "DoorsTask", "build_doors_trials", "format_doors_feedback"]
