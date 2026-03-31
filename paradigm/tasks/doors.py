import random
from dataclasses import dataclass

from psychopy import visual

from paradigm.config import AppConfig, DoorsTaskConfig
from paradigm.runtime import AOIRegion, BaseExperiment, SafeExitRequested
from paradigm.runtime.utils import balanced_binary_sequence


@dataclass(slots=True)
class DoorTrial:
    block: int
    trial_index: int
    feedback_type: str


def format_doors_feedback(trial: DoorTrial, task_config: DoorsTaskConfig) -> tuple[str, str, int]:
    feedback_value = task_config.gain_value if trial.feedback_type == "gain" else task_config.loss_value
    color = "lightgreen" if trial.feedback_type == "gain" else "tomato"
    if task_config.feedback_display_mode == "label":
        text = task_config.gain_label if trial.feedback_type == "gain" else task_config.loss_label
    else:
        text = f"{feedback_value:+d}"
    return text, color, feedback_value


def build_doors_trials(task_config: DoorsTaskConfig, rng: random.Random) -> list[DoorTrial]:
    total_trials = task_config.blocks * task_config.trials_per_block
    sequence = balanced_binary_sequence(total_trials, rng)
    trials: list[DoorTrial] = []
    for block in range(1, task_config.blocks + 1):
        for trial_in_block in range(1, task_config.trials_per_block + 1):
            global_index = (block - 1) * task_config.trials_per_block + trial_in_block
            feedback_type = "gain" if sequence[global_index - 1] == 1 else "loss"
            trials.append(DoorTrial(block=block, trial_index=global_index, feedback_type=feedback_type))
    return trials


class DoorsTask(BaseExperiment):
    def __init__(self, participant: str, session: str, config: AppConfig | None = None) -> None:
        super().__init__(task_name="doors", participant=participant, session=session, config=config)
        self.task_config = self.config.doors
        self.left_door = visual.Rect(self.window, width=0.18, height=0.32, pos=(-0.25, 0), lineColor="white", fillColor=None, lineWidth=3)
        self.right_door = visual.Rect(self.window, width=0.18, height=0.32, pos=(0.25, 0), lineColor="white", fillColor=None, lineWidth=3)
        self.left_label = visual.TextStim(self.window, text="左", pos=(-0.25, -0.24), height=0.035, color="white")
        self.right_label = visual.TextStim(self.window, text="右", pos=(0.25, -0.24), height=0.035, color="white")
        self.feedback_text = visual.TextStim(self.window, text="", height=0.08, color="white")
        self.choice_aois = [AOIRegion(name="left_door", left=-0.34, right=-0.16, bottom=-0.16, top=0.16), AOIRegion(name="right_door", left=0.16, right=0.34, bottom=-0.16, top=0.16)]
        self._trials = build_doors_trials(self.task_config, self.rng)

    def _draw_choice_screen(self, selected: str | None = None) -> None:
        self.left_door.fillColor = "darkgreen" if selected == "left" else None
        self.right_door.fillColor = "darkgreen" if selected == "right" else None
        self.left_door.draw()
        self.right_door.draw()
        self.left_label.draw()
        self.right_label.draw()

    def _draw_feedback(self) -> None:
        self.feedback_text.draw()

    @staticmethod
    def _event(name: str) -> str:
        return f"doors.{name}"

    def run(self) -> None:
        total_trials = len(self._trials)
        mode_prefix = "练习模式：" if self.config.practice.enabled else ""
        trial_rows: list[dict] = []
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

                    lsl_codes: list[int] = [self.task_config.marker_codes[choice_event]]
                    lpt_codes: list[int] = [self.task_config.marker_codes[choice_event]]
                    event_keys: list[str] = [choice_event]
                    fnirs_codes: list[int] = []
                    choice_fnirs = self.fnirs_code_for(self.task_config.marker_codes[choice_event])
                    if choice_fnirs is not None:
                        fnirs_codes.append(choice_fnirs)
                    response_label = response_data["response"]
                    timeout = response_data["timeout"]

                    if timeout:
                        timeout_marker = self.send_marker_now(event_name=timeout_event, metadata={"task": self.task_name, "block": block, "trial": trial.trial_index}, block=block, trial=trial.trial_index)
                        lsl_codes.append(timeout_marker.code if timeout_marker.lsl_sent else -1)
                        lpt_codes.append(timeout_marker.code if timeout_marker.lpt_sent else -1)
                        event_keys.append(timeout_marker.label or timeout_event)
                        if timeout_marker.fnirs_sent:
                            fnirs_codes.append(timeout_marker.payload.get("fnirs_code", -1))
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
                        lsl_codes.append(response_marker.code if response_marker.lsl_sent else -1)
                        lpt_codes.append(response_marker.code if response_marker.lpt_sent else -1)
                        event_keys.append(response_marker.label or response_event_name)
                        if response_marker.fnirs_sent:
                            fnirs_codes.append(response_marker.payload.get("fnirs_code", -1))
                        response_event = response_marker.label or response_event_name
                        feedback_event_name = feedback_gain_event if trial.feedback_type == "gain" else feedback_loss_event
                        feedback_code = self.task_config.marker_codes[feedback_event_name]
                        feedback_text, feedback_color, feedback_value = format_doors_feedback(trial, self.task_config)
                        displayed_feedback = trial.feedback_type
                        feedback_semantics = "outcome"

                    post_choice_delay_onset = self.present_timed_event(
                        draw_fn=lambda: self._draw_choice_screen(selected=response_label),
                        duration_s=self.task_config.post_choice_delay_s,
                        event_code=None,
                        label=None,
                        event_name=post_choice_event,
                        block=block,
                        trial=trial.trial_index,
                        metadata={"task": self.task_name, "block": block, "trial": trial.trial_index},
                    )
                    lsl_codes.append(self.task_config.marker_codes[post_choice_event])
                    lpt_codes.append(self.task_config.marker_codes[post_choice_event])
                    event_keys.append(post_choice_event)
                    post_delay_fnirs = self.fnirs_code_for(self.task_config.marker_codes[post_choice_event])
                    if post_delay_fnirs is not None:
                        fnirs_codes.append(post_delay_fnirs)

                    self.feedback_text.text = feedback_text
                    self.feedback_text.color = feedback_color
                    feedback_onset = self.present_timed_event(
                        draw_fn=self._draw_feedback,
                        duration_s=self.task_config.feedback_s,
                        event_code=None,
                        label=None,
                        event_name=feedback_event_name,
                        block=block,
                        trial=trial.trial_index,
                        metadata={"task": self.task_name, "block": block, "trial": trial.trial_index, "feedback_type": trial.feedback_type, "feedback_value": feedback_value},
                    )
                    lsl_codes.append(feedback_code)
                    lpt_codes.append(feedback_code)
                    event_keys.append(feedback_event_name)
                    feedback_fnirs = self.fnirs_code_for(feedback_code)
                    if feedback_fnirs is not None:
                        fnirs_codes.append(feedback_fnirs)

                    iti_duration = self.sample_iti(self.task_config.iti_range_s)
                    iti_onset = self.present_timed_event(draw_fn=self.fixation.draw, duration_s=iti_duration, event_code=None, label=None, event_name=iti_event, block=block, trial=trial.trial_index, metadata={"task": self.task_name, "block": block, "trial": trial.trial_index, "iti_s": iti_duration})
                    lsl_codes.append(self.task_config.marker_codes[iti_event])
                    lpt_codes.append(self.task_config.marker_codes[iti_event])
                    event_keys.append(iti_event)
                    iti_fnirs = self.fnirs_code_for(self.task_config.marker_codes[iti_event])
                    if iti_fnirs is not None:
                        fnirs_codes.append(iti_fnirs)

                    exclude_trial = timeout
                    exclude_reason = "timeout" if timeout else None
                    invalid_response = timeout

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
                                "post_choice_delay_onset": post_choice_delay_onset,
                                "scheduled_feedback_type": trial.feedback_type,
                                "feedback_type": displayed_feedback,
                                "feedback_semantics": feedback_semantics,
                                "feedback_value": feedback_value,
                                "feedback_display_mode": self.task_config.feedback_display_mode,
                                "response_event": response_event,
                                "feedback_event": feedback_event_name,
                                "exclude_trial": exclude_trial,
                                "exclude_reason": exclude_reason,
                                "invalid_response": invalid_response,
                            },
                        }
                    self.log_trial_row(trial_row)
                    trial_rows.append(trial_row)

                    if trial_in_block < self.task_config.trials_per_block and trial_in_block % self.config.common.break_every_n_trials == 0:
                        self.show_break(block=block, completed_trials=trial.trial_index, total_trials=total_trials)

                self.send_marker_now(event_name=self._event("block.end"), metadata={"task": self.task_name, "block": block}, block=block)

            self.send_marker_now(event_name=self._event("experiment.end"), metadata={"task": self.task_name})
            gain_trials = sum(1 for row in trial_rows if row["feedback"] == "gain")
            loss_trials = sum(1 for row in trial_rows if row["feedback"] == "loss")
            timeout_trials = sum(1 for row in trial_rows if row["feedback"] == "timeout")
            feedback_event_complete = all(any(name.startswith("doors.feedback.") for name in row["event_keys"]) for row in trial_rows)
            self.run_summary = {
                "n_trials": len(trial_rows),
                "timeout_rate": (sum(1 for row in trial_rows if row["timeout"]) / len(trial_rows)) if trial_rows else None,
                "gain_trials": gain_trials,
                "loss_trials": loss_trials,
                "timeout_trials": timeout_trials,
                "feedback_event_complete": feedback_event_complete,
                "task_positioning": "rapid feedback-chain validation for feedback-locked EEG, RewP/FRN, and feedback-theta checks",
            }
            self.final_status = "completed"
            self.show_message(f"{mode_prefix}Doors 任务已完成。\n\n按 {self.continue_key_label()} 结束。")
        except SafeExitRequested:
            self.final_status = "safe_exit"
            self.log_event(event_name="system.safe_exit.requested")
        finally:
            self.finalize()
