from paradigm.config import AppConfig
from paradigm.hardware.eyetracking import AOIRegion
from paradigm.runtime.base_experiment import BaseExperiment, SafeExitRequested
from paradigm.runtime.choice_panels import ChoicePanelPair
from paradigm.analysis.prl import summarize_prl_run
from paradigm.tasks.prl.prl_logic import PRLFeedbackOutcome, PRLTrialState, ReversalEngine, RescorlaWagnerAgent, classify_prl_expectedness, classify_prl_trial_phase, resolve_prl_timeout_policy


class PRLTask(BaseExperiment):
    def __init__(self, participant: str, session: str, config: AppConfig | None = None) -> None:
        from psychopy import visual

        super().__init__(task_name="prl", participant=participant, session=session, config=config)
        self.task_config = self.config.prl
        self.reversal_engine = ReversalEngine(
            blocks=self.task_config.blocks,
            trials_per_block=self.task_config.trials_per_block,
            reward_probability_good=self.task_config.reward_probability_good,
            reward_probability_bad=self.task_config.reward_probability_bad,
            criterion_window=self.task_config.criterion_window,
            criterion_optimal_choices=self.task_config.criterion_optimal_choices,
            min_trials_before_reversal=self.task_config.min_trials_before_reversal,
            stimulus_labels=self.task_config.stimulus_labels,
            rng=self.rng,
        )
        self.choice_panels = ChoicePanelPair(visual, self.window, left_label="A", right_label="B", text_font=self.text_font)
        self.feedback_text = visual.TextStim(self.window, text="", pos=(0, 0), height=0.08, color="white", font=self.text_font)
        self.choice_aois = self.choice_panels.build_aois(left_name="left_option", right_name="right_option")
        self.rl_agent = RescorlaWagnerAgent(
            positive_learning_rate=self.task_config.positive_learning_rate,
            negative_learning_rate=self.task_config.negative_learning_rate,
            inverse_temperature=self.task_config.inverse_temperature,
            stickiness=self.task_config.stickiness,
            initial_q=self.task_config.initial_q,
            stimulus_labels=self.task_config.stimulus_labels,
        )

    def _configure_layout(self, state: PRLTrialState) -> None:
        self.choice_panels.set_labels(left_label=state.left_stimulus, right_label=state.right_stimulus)

    def _draw_choice_screen(self, selected: str | None = None) -> None:
        self.choice_panels.draw(selected=selected)

    def _draw_feedback(self) -> None:
        self.feedback_text.draw()

    @staticmethod
    def _event(name: str) -> str:
        return f"prl.{name}"

    def run(self) -> None:
        total_trials = self.task_config.blocks * self.task_config.trials_per_block
        mode_prefix = "练习模式：" if self.config.practice.enabled else ""
        trial_rows: list[dict] = []
        try:
            self.show_labrecorder_wait_screen()
            self.experiment_clock.reset()
            self.send_marker_now(event_name=self._event("experiment.start"), metadata={"task": self.task_name})
            self.show_message(
                f"{mode_prefix}概率反转学习任务\n\n请使用左右方向键在固定的 A / B 两个刺激之间做选择。\nA 始终在左侧，B 始终在右侧；屏幕不会提示哪一个刺激当前拥有更高获奖概率。\n当你的选择正确率达到准则后，背后的高概率刺激会在无预警情况下隐藏反转。\n\n按 {self.continue_key_label()} 开始。"
            )

            previous_choice_stimulus = None
            previous_feedback = None

            for global_trial in range(1, total_trials + 1):
                state = self.reversal_engine.get_trial_state(global_trial)
                self._configure_layout(state)
                fixation_event = self._event("fixation.onset")
                choice_event = self._event("choice.onset")
                timeout_event = self._event("response.timeout")
                response_left_event = self._event("response.left")
                response_right_event = self._event("response.right")
                post_choice_event = self._event("post_choice_delay.onset")
                feedback_reward_event = self._event("feedback.reward")
                feedback_no_reward_event = self._event("feedback.no_reward")
                iti_event = self._event("iti.onset")
                if state.trial_in_block == 1:
                    self.send_marker_now(event_name=self._event("block.start"), metadata={"task": self.task_name, "block": state.block, "good_stimulus": state.good_stimulus}, block=state.block, trial=state.trial_index)
                if state.is_reversal_boundary:
                    self.send_marker_now(event_name=self._event("reversal.boundary"), metadata={"task": self.task_name, "block": state.block, "good_stimulus": state.good_stimulus, "reversal_index": state.reversal_index}, block=state.block, trial=state.trial_index)

                fixation_onset = self.fixation_period(duration_s=self.task_config.fixation_s, event_name=fixation_event, block=state.block, trial=state.trial_index)
                response_data = self.wait_for_response(
                    draw_fn=self._draw_choice_screen,
                    valid_keys=self.task_config.response_keys,
                    timeout_s=self.task_config.response_timeout_s,
                    onset_event_code=None,
                    onset_label=None,
                    onset_event_name=choice_event,
                    block=state.block,
                    trial=state.trial_index,
                    metadata={"task": self.task_name, "block": state.block, "trial": state.trial_index},
                )
                self.poll_and_log_aoi(aoi_regions=self.choice_aois, block=state.block, trial=state.trial_index)
                response = response_data["response"]
                timeout = response_data["timeout"]
                lsl_codes: list[int] = []
                lpt_codes: list[int] = []
                event_keys: list[str] = [choice_event]
                fnirs_codes: list[int] = []
                self.append_marker_result_codes(response_data["onset_marker"], lsl_codes=lsl_codes, lpt_codes=lpt_codes, fnirs_codes=fnirs_codes)

                chosen_stimulus = None
                unchosen_stimulus = None
                optimal_choice = None
                reward = None
                misleading_feedback = None
                signed_prediction_error = None
                unsigned_prediction_error = None
                outcome_expectedness = None
                stimulus_a_value = self.rl_agent.q_values[self.task_config.stimulus_labels[0]]
                stimulus_b_value = self.rl_agent.q_values[self.task_config.stimulus_labels[1]]
                left_choice_probability = self.rl_agent.choice_probability_left(
                    left_stimulus=state.left_stimulus,
                    right_stimulus=state.right_stimulus,
                    previous_choice_stimulus=previous_choice_stimulus,
                )
                switch_from_previous = None
                chosen_value = None
                unchosen_value = None
                trial_phase = classify_prl_trial_phase(
                    state,
                    early_post_reversal_trials=self.task_config.early_post_reversal_trials,
                    relearning_trials=self.task_config.relearning_trials,
                )
                timeout_policy = resolve_prl_timeout_policy(timeout)
                criterion_update = self.reversal_engine.update_after_trial(optimal_choice=None, timeout=True) if timeout else None
                if timeout:
                    timeout_marker = self.send_marker_now(event_name=timeout_event, metadata={"task": self.task_name, "block": state.block, "trial": state.trial_index}, block=state.block, trial=state.trial_index)
                    event_keys.append(timeout_marker.label or timeout_event)
                    self.append_marker_result_codes(timeout_marker, lsl_codes=lsl_codes, lpt_codes=lpt_codes, fnirs_codes=fnirs_codes)
                    response_event = timeout_event
                    feedback_label = "timeout"
                    feedback_event_name = self._event("feedback.timeout")
                    feedback_code = self.task_config.marker_codes[feedback_event_name]
                    self.feedback_text.text = self.task_config.timeout_feedback_text
                    self.feedback_text.color = "gold"
                    post_choice_delay_onset = None
                else:
                    response_event_name = response_left_event if response == "left" else response_right_event
                    response_marker = self.send_marker_now(event_name=response_event_name, metadata={"task": self.task_name, "block": state.block, "trial": state.trial_index, "rt": response_data["rt"]}, block=state.block, trial=state.trial_index)
                    event_keys.append(response_marker.label or response_event_name)
                    self.append_marker_result_codes(response_marker, lsl_codes=lsl_codes, lpt_codes=lpt_codes, fnirs_codes=fnirs_codes)
                    response_event = response_marker.label or response_event_name
                    outcome: PRLFeedbackOutcome = self.reversal_engine.resolve_feedback_for_state(state, response)
                    chosen_stimulus = outcome.chosen_stimulus
                    unchosen_stimulus = outcome.unchosen_stimulus
                    optimal_choice = outcome.optimal_choice
                    reward = outcome.reward
                    misleading_feedback = outcome.misleading_feedback
                    chosen_value = self.rl_agent.q_values[chosen_stimulus]
                    unchosen_value = self.rl_agent.q_values[unchosen_stimulus]
                    signed_prediction_error, unsigned_prediction_error = self.rl_agent.update(chosen_stimulus, reward)
                    criterion_update = self.reversal_engine.update_after_trial(optimal_choice=optimal_choice, timeout=False)
                    switch_from_previous = chosen_stimulus != previous_choice_stimulus if previous_choice_stimulus is not None else None
                    previous_choice_stimulus = chosen_stimulus
                    outcome_expectedness = classify_prl_expectedness(optimal_choice, reward)

                    if reward:
                        feedback_label = "reward"
                        feedback_event_name = feedback_reward_event
                        feedback_code = self.task_config.marker_codes[feedback_event_name]
                        self.feedback_text.text = f"+{self.task_config.reward_value}"
                        self.feedback_text.color = "lightgreen"
                    else:
                        feedback_label = "no_reward"
                        feedback_event_name = feedback_no_reward_event
                        feedback_code = self.task_config.marker_codes[feedback_event_name]
                        self.feedback_text.text = str(self.task_config.no_reward_value)
                        self.feedback_text.color = "tomato"

                    post_choice_delay = self.sample_iti(self.task_config.post_choice_delay_range_s)
                    post_choice_delay_onset, post_choice_delay_marker = self.present_timed_event(
                        draw_fn=lambda: self._draw_choice_screen(selected=response),
                        duration_s=post_choice_delay,
                        event_code=None,
                        label=None,
                        event_name=post_choice_event,
                        block=state.block,
                        trial=state.trial_index,
                        metadata={"task": self.task_name, "block": state.block, "trial": state.trial_index},
                    )
                    event_keys.append(post_choice_event)
                    self.append_marker_result_codes(post_choice_delay_marker, lsl_codes=lsl_codes, lpt_codes=lpt_codes, fnirs_codes=fnirs_codes)

                feedback_onset, feedback_marker = self.present_timed_event(
                    draw_fn=self._draw_feedback,
                    duration_s=self.task_config.feedback_s,
                    event_code=None,
                    label=None,
                    event_name=feedback_event_name,
                    block=state.block,
                    trial=state.trial_index,
                    metadata={"task": self.task_name, "block": state.block, "trial": state.trial_index, "reward": reward, "good_stimulus": state.good_stimulus, "optimal_choice": optimal_choice},
                )
                event_keys.append(feedback_event_name)
                self.append_marker_result_codes(feedback_marker, lsl_codes=lsl_codes, lpt_codes=lpt_codes, fnirs_codes=fnirs_codes)

                iti_duration = self.sample_iti(self.task_config.iti_range_s)
                iti_onset, iti_marker = self.present_timed_event(draw_fn=self.fixation.draw, duration_s=iti_duration, event_code=None, label=None, event_name=iti_event, block=state.block, trial=state.trial_index, metadata={"task": self.task_name, "block": state.block, "trial": state.trial_index, "iti_s": iti_duration})
                event_keys.append(iti_event)
                self.append_marker_result_codes(iti_marker, lsl_codes=lsl_codes, lpt_codes=lpt_codes, fnirs_codes=fnirs_codes)

                trial_row = {
                        "participant": self.participant,
                        "session": self.session,
                        "task": self.task_name,
                        "block": state.block,
                        "trial_index": state.trial_index,
                        "condition": f"optimal_{state.good_stimulus}",
                        "stimulus_parameters": {
                            "good_stimulus": state.good_stimulus,
                            "left_stimulus": state.left_stimulus,
                            "right_stimulus": state.right_stimulus,
                            "stimulus_positions_fixed": True,
                            "reward_probability_good": self.task_config.reward_probability_good,
                            "reward_probability_bad": self.task_config.reward_probability_bad,
                            "trial_in_block": state.trial_in_block,
                            "reversal_index": state.reversal_index,
                            "is_reversal_boundary": state.is_reversal_boundary,
                        },
                        "response": response,
                        "rt": response_data["rt"],
                        "correct": optimal_choice,
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
                            "good_stimulus": state.good_stimulus,
                            "chosen_stimulus": chosen_stimulus,
                            "unchosen_stimulus": unchosen_stimulus,
                            "left_stimulus": state.left_stimulus,
                            "right_stimulus": state.right_stimulus,
                            "stimulus_positions_fixed": True,
                            "reward": reward,
                            "optimal_choice": optimal_choice,
                            "misleading_feedback": misleading_feedback,
                            "reversal_index": state.reversal_index,
                            "reversal_trial_offset": state.trials_since_reversal,
                            "trial_phase": trial_phase,
                            "outcome_expectedness": outcome_expectedness,
                            "response_event": response_event,
                            "feedback_event": feedback_event_name,
                            "post_choice_delay_onset": post_choice_delay_onset,
                            "stimulus_A_value": stimulus_a_value,
                            "stimulus_B_value": stimulus_b_value,
                            "chosen_value": chosen_value,
                            "unchosen_value": unchosen_value,
                            "signed_prediction_error": signed_prediction_error,
                            "unsigned_prediction_error": unsigned_prediction_error,
                            "left_choice_probability": left_choice_probability,
                            "switch_from_previous": switch_from_previous,
                            "previous_feedback": previous_feedback,
                            "rl_update_applied": timeout_policy["rl_update_applied"],
                            "counted_for_choice_dynamics": timeout_policy["counted_for_choice_dynamics"],
                            "timeout_feedback_presented": timeout_policy["timeout_feedback_presented"],
                            "criterion_reached": criterion_update["criterion_reached"] if criterion_update else False,
                            "trials_to_criterion": criterion_update["trials_to_criterion"] if criterion_update else None,
                            "exclude_trial": timeout_policy["exclude_trial"],
                            "exclude_reason": timeout_policy["exclude_reason"],
                            "invalid_response": timeout_policy["invalid_response"],
                            "first_fixation_aoi": None,
                            "last_fixation_aoi": None,
                            "dwell_left_s": None,
                            "dwell_right_s": None,
                            "dwell_asymmetry": None,
                            "exploration_after_reversal": None,
                            "aoi_summary_available": False,
                        },
                    }
                self.log_trial_row(trial_row)
                summary_row = dict(trial_row)
                summary_row.update(trial_row["task_specific_data"])
                trial_rows.append(summary_row)
                previous_feedback = feedback_label

                if state.trial_in_block == self.task_config.trials_per_block:
                    self.send_marker_now(event_name=self._event("block.end"), metadata={"task": self.task_name, "block": state.block}, block=state.block, trial=state.trial_index)
                    if state.block < self.task_config.blocks:
                        self.show_break(block=state.block, completed_trials=state.trial_index, total_trials=total_trials)

            self.send_marker_now(event_name=self._event("experiment.end"), metadata={"task": self.task_name})
            self.run_summary = summarize_prl_run(trial_rows)
            self.run_summary["reversal_count"] = self.reversal_engine.reversal_index
            self.run_summary["task_positioning"] = "probabilistic reversal learning task for hidden contingency updates, FRN/P3/theta, and trial-wise RL signals"
            self.final_status = "completed"
            self.show_message(f"{mode_prefix}PRL 任务已完成。\n\n按 {self.continue_key_label()} 结束。")
        except SafeExitRequested:
            self.final_status = "safe_exit"
            self.log_event(event_name="system.safe_exit.requested")
        finally:
            self.finalize()


__all__ = [
    "PRLTask",
    "PRLTrialState",
    "RescorlaWagnerAgent",
    "ReversalEngine",
    "classify_prl_expectedness",
    "classify_prl_trial_phase",
    "resolve_prl_timeout_policy",
]
