import random
import tempfile
import unittest
from pathlib import Path

from paradigm.analysis.rdm import export_chronometric_summary, export_ddm_ready_table, export_psychometric_summary
from paradigm.config import DoorsTaskConfig, PRLTaskConfig, RDMTaskConfig
from paradigm.tasks.doors.doors import DoorTrial, build_doors_trials, format_doors_feedback
from paradigm.tasks.prl.prl import PRLTrialState, RescorlaWagnerAgent, ReversalEngine, classify_prl_expectedness, classify_prl_trial_phase, resolve_prl_timeout_policy
from paradigm.tasks.rdm.rdm import build_rdm_trials, determine_rdm_trial_quality, resolve_rdm_feedback_plan


class StaticRng:
    def __init__(self, values: list[float]) -> None:
        self._values = values
        self._index = 0

    def random(self) -> float:
        value = self._values[self._index]
        self._index += 1
        return value


class TaskGenerationTests(unittest.TestCase):
    def test_build_doors_trials_is_balanced(self) -> None:
        config = DoorsTaskConfig(blocks=2, trials_per_block=4)
        trials = build_doors_trials(config, random.Random(1234))

        self.assertEqual(len(trials), 8)
        feedback_types = [trial.feedback_type for trial in trials]
        self.assertEqual(feedback_types.count("gain"), 4)
        self.assertEqual(feedback_types.count("loss"), 4)
        for block in (1, 2):
            block_feedback = [trial.feedback_type for trial in trials if trial.block == block]
            self.assertEqual(block_feedback.count("gain"), 2)
            self.assertEqual(block_feedback.count("loss"), 2)

    def test_format_doors_feedback_supports_numeric_and_label_modes(self) -> None:
        numeric_config = DoorsTaskConfig(feedback_display_mode="numeric", gain_value=10, loss_value=-5)
        label_config = DoorsTaskConfig(feedback_display_mode="label", gain_label="WIN", loss_label="LOSS")
        gain_trial = DoorTrial(block=1, trial_index=1, feedback_type="gain")
        loss_trial = DoorTrial(block=1, trial_index=2, feedback_type="loss")

        self.assertEqual(format_doors_feedback(gain_trial, numeric_config), ("+10", "lightgreen", 10))
        self.assertEqual(format_doors_feedback(loss_trial, label_config), ("LOSS", "tomato", -5))

    def test_reversal_engine_sets_boundaries_and_feedback(self) -> None:
        engine = ReversalEngine(
            blocks=2,
            trials_per_block=3,
            reward_probability_good=0.8,
            reward_probability_bad=0.2,
            criterion_window=3,
            criterion_optimal_choices=3,
            min_trials_before_reversal=3,
            stimulus_labels=("A", "B"),
            rng=StaticRng([0.1, 0.1, 0.1, 0.9]),
        )
        first_state = engine.get_trial_state(1)
        outcome = engine.resolve_feedback_for_state(first_state, "left")
        update = engine.update_after_trial(optimal_choice=outcome.optimal_choice, timeout=False)

        second_state = engine.get_trial_state(2)
        outcome = engine.resolve_feedback_for_state(second_state, "left")
        update = engine.update_after_trial(optimal_choice=outcome.optimal_choice, timeout=False)

        third_state = engine.get_trial_state(3)
        outcome = engine.resolve_feedback_for_state(third_state, "left")
        update = engine.update_after_trial(optimal_choice=outcome.optimal_choice, timeout=False)
        fourth_state = engine.get_trial_state(4)

        self.assertEqual(first_state.good_stimulus, "A")
        self.assertEqual(first_state.left_stimulus, "A")
        self.assertEqual(first_state.right_stimulus, "B")
        self.assertFalse(first_state.is_reversal_boundary)
        self.assertTrue(update["criterion_reached"])
        self.assertEqual(fourth_state.good_stimulus, "B")
        self.assertTrue(fourth_state.is_reversal_boundary)
        self.assertEqual(fourth_state.trials_since_reversal, 0)
        self.assertEqual(fourth_state.left_stimulus, "A")
        self.assertEqual(fourth_state.right_stimulus, "B")

        fourth_outcome = engine.resolve_feedback_for_state(fourth_state, "left")
        self.assertFalse(fourth_outcome.optimal_choice)
        self.assertFalse(fourth_outcome.reward)

    def test_reversal_engine_requires_current_correct_trial_to_schedule_reversal(self) -> None:
        engine = ReversalEngine(
            blocks=2,
            trials_per_block=3,
            reward_probability_good=0.8,
            reward_probability_bad=0.2,
            criterion_window=3,
            criterion_optimal_choices=2,
            min_trials_before_reversal=3,
            stimulus_labels=("A", "B"),
            rng=StaticRng([0.1, 0.1, 0.9, 0.1]),
        )

        first_state = engine.get_trial_state(1)
        first_outcome = engine.resolve_feedback_for_state(first_state, "left")
        engine.update_after_trial(optimal_choice=first_outcome.optimal_choice, timeout=False)

        second_state = engine.get_trial_state(2)
        second_outcome = engine.resolve_feedback_for_state(second_state, "left")
        engine.update_after_trial(optimal_choice=second_outcome.optimal_choice, timeout=False)

        third_state = engine.get_trial_state(3)
        third_outcome = engine.resolve_feedback_for_state(third_state, "right")
        third_update = engine.update_after_trial(optimal_choice=third_outcome.optimal_choice, timeout=False)
        self.assertFalse(third_update["criterion_reached"])

        fourth_state = engine.get_trial_state(4)
        fourth_outcome = engine.resolve_feedback_for_state(fourth_state, "left")
        fourth_update = engine.update_after_trial(optimal_choice=fourth_outcome.optimal_choice, timeout=False)
        self.assertTrue(fourth_update["criterion_reached"])

    def test_rl_agent_updates_q_values(self) -> None:
        agent = RescorlaWagnerAgent(
            positive_learning_rate=0.5,
            negative_learning_rate=0.25,
            inverse_temperature=2.0,
            stickiness=0.2,
            initial_q=0.5,
            stimulus_labels=("A", "B"),
        )
        signed_pe, unsigned_pe = agent.update("A", True)
        self.assertAlmostEqual(signed_pe, 0.5)
        self.assertAlmostEqual(unsigned_pe, 0.5)
        self.assertAlmostEqual(agent.q_values["A"], 0.75)
        self.assertGreater(agent.choice_probability_left(left_stimulus="A", right_stimulus="B"), 0.5)

    def test_prl_expectedness_and_phase_helpers(self) -> None:
        state_initial = PRLTrialState(block=1, trial_index=3, trial_in_block=3, reversal_index=0, good_stimulus="A", left_stimulus="A", right_stimulus="B", is_reversal_boundary=False, trials_since_reversal=2)
        state_early = PRLTrialState(block=2, trial_index=41, trial_in_block=1, reversal_index=1, good_stimulus="B", left_stimulus="A", right_stimulus="B", is_reversal_boundary=True, trials_since_reversal=0)
        state_relearning = PRLTrialState(block=2, trial_index=48, trial_in_block=8, reversal_index=1, good_stimulus="B", left_stimulus="A", right_stimulus="B", is_reversal_boundary=False, trials_since_reversal=7)
        state_stable = PRLTrialState(block=2, trial_index=60, trial_in_block=20, reversal_index=1, good_stimulus="B", left_stimulus="A", right_stimulus="B", is_reversal_boundary=False, trials_since_reversal=18)

        self.assertEqual(classify_prl_expectedness(True, True), "expected_reward")
        self.assertEqual(classify_prl_expectedness(True, False), "unexpected_no_reward")
        self.assertEqual(classify_prl_expectedness(False, True), "unexpected_reward")
        self.assertEqual(classify_prl_expectedness(False, False), "expected_no_reward")

        self.assertEqual(
            classify_prl_trial_phase(state_initial, early_post_reversal_trials=5, relearning_trials=10),
            "initial_learning",
        )
        self.assertEqual(
            classify_prl_trial_phase(state_early, early_post_reversal_trials=5, relearning_trials=10),
            "early_post_reversal",
        )
        self.assertEqual(
            classify_prl_trial_phase(state_relearning, early_post_reversal_trials=5, relearning_trials=10),
            "relearning",
        )
        self.assertEqual(
            classify_prl_trial_phase(state_stable, early_post_reversal_trials=5, relearning_trials=10),
            "stable",
        )

    def test_prl_timeout_policy_excludes_trial_and_skips_rl_update(self) -> None:
        timeout_policy = resolve_prl_timeout_policy(True)
        valid_policy = resolve_prl_timeout_policy(False)
        self.assertFalse(timeout_policy["rl_update_applied"])
        self.assertFalse(timeout_policy["counted_for_choice_dynamics"])
        self.assertTrue(timeout_policy["timeout_feedback_presented"])
        self.assertTrue(timeout_policy["exclude_trial"])
        self.assertEqual(timeout_policy["exclude_reason"], "timeout")
        self.assertTrue(valid_policy["rl_update_applied"])

    def test_build_rdm_trials_covers_conditions(self) -> None:
        config = RDMTaskConfig(blocks=2, trials_per_signed_coherence=1, signed_coherence_levels=[-0.3, -0.1, 0.1, 0.3])
        trials = build_rdm_trials(config, random.Random(99))

        self.assertEqual(len(trials), 4)
        conditions = {(trial.direction, trial.signed_coherence) for trial in trials}
        self.assertEqual(conditions, {("left", -0.3), ("left", -0.1), ("right", 0.1), ("right", 0.3)})

    def test_rdm_export_helpers_write_files(self) -> None:
        rows = [
            {"trial_index": 1, "signed_coherence": -0.1, "absolute_coherence": 0.1, "direction": "left", "response": "left", "correct": True, "rt": 0.4, "timeout": False, "response_locked_rt": 0.4, "cpp_slope_proxy": 0.25, "exclude_trial": None, "exclude_reason": None},
            {"trial_index": 2, "signed_coherence": 0.1, "absolute_coherence": 0.1, "direction": "right", "response": "left", "correct": False, "rt": 0.6, "timeout": False, "response_locked_rt": 0.6, "cpp_slope_proxy": 0.166, "exclude_trial": None, "exclude_reason": None},
        ]
        with tempfile.TemporaryDirectory() as tmp_dir:
            psychometric_path = Path(tmp_dir) / "psychometric.csv"
            chronometric_path = Path(tmp_dir) / "chronometric.csv"
            ddm_path = Path(tmp_dir) / "ddm.csv"
            export_psychometric_summary(rows, psychometric_path)
            export_chronometric_summary(rows, chronometric_path)
            export_ddm_ready_table(rows, ddm_path)
            self.assertTrue(psychometric_path.exists())
            self.assertTrue(chronometric_path.exists())
            self.assertTrue(ddm_path.exists())

    def test_rdm_feedback_plan_and_quality_flags(self) -> None:
        self.assertEqual(resolve_rdm_feedback_plan(correct=True, timeout=False, feedback_mode="correctness"), ("correct", "feedback.correct", "正确"))
        self.assertEqual(resolve_rdm_feedback_plan(correct=False, timeout=True, feedback_mode="correctness"), ("timeout", "feedback.timeout", "反应过慢"))
        self.assertEqual(resolve_rdm_feedback_plan(correct=False, timeout=False, feedback_mode="correctness"), ("error", "feedback.error", "错误"))
        self.assertEqual(resolve_rdm_feedback_plan(correct=False, timeout=False, feedback_mode="none"), ("omitted", None, None))

        self.assertEqual(
            determine_rdm_trial_quality(timeout=True, fixation_break_detected=False, invalid_response=False, exclude_timeouts_from_analysis=True),
            (True, "timeout"),
        )
        self.assertEqual(
            determine_rdm_trial_quality(timeout=False, fixation_break_detected=True, invalid_response=False, exclude_timeouts_from_analysis=True),
            (True, "fixation_break"),
        )
        self.assertEqual(
            determine_rdm_trial_quality(timeout=False, fixation_break_detected=False, invalid_response=False, exclude_timeouts_from_analysis=True),
            (False, None),
        )
        self.assertEqual(
            determine_rdm_trial_quality(timeout=False, fixation_break_detected=False, invalid_response=True, exclude_timeouts_from_analysis=True),
            (True, "invalid_response"),
        )
