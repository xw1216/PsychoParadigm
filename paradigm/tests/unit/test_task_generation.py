import random
import tempfile
import unittest
from pathlib import Path

from paradigm.config import DoorsTaskConfig, PRLTaskConfig, RDMTaskConfig
from paradigm.tasks.doors.doors import DoorTrial, build_doors_trials, format_doors_feedback
from paradigm.tasks.prl.prl import PRLTrialState, RescorlaWagnerAgent, ReversalEngine, classify_prl_expectedness, classify_prl_trial_phase, resolve_prl_timeout_policy
from paradigm.tasks.rdm.rdm import RDMTask, build_rdm_trials, determine_rdm_trial_quality, resolve_rdm_feedback_plan


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

    def test_format_doors_feedback_supports_numeric_and_label_modes(self) -> None:
        numeric_config = DoorsTaskConfig(feedback_display_mode="numeric", gain_value=10, loss_value=-5)
        label_config = DoorsTaskConfig(feedback_display_mode="label", gain_label="WIN", loss_label="LOSS")
        gain_trial = DoorTrial(block=1, trial_index=1, feedback_type="gain")
        loss_trial = DoorTrial(block=1, trial_index=2, feedback_type="loss")

        self.assertEqual(format_doors_feedback(gain_trial, numeric_config), ("+10", "lightgreen", 10))
        self.assertEqual(format_doors_feedback(loss_trial, label_config), ("LOSS", "tomato", -5))

    def test_reversal_engine_sets_boundaries_and_feedback(self) -> None:
        engine = ReversalEngine(blocks=2, trials_per_block=3, reward_probability_good=0.8, reward_probability_bad=0.2, rng=StaticRng([0.1, 0.9]))
        first_state = engine.get_trial_state(1)
        fourth_state = engine.get_trial_state(4)

        self.assertEqual(first_state.good_side, "left")
        self.assertFalse(first_state.is_reversal_boundary)
        self.assertEqual(fourth_state.good_side, "right")
        self.assertTrue(fourth_state.is_reversal_boundary)

        chosen_good, reward = engine.resolve_feedback_for_state(first_state, "left")
        self.assertTrue(chosen_good)
        self.assertTrue(reward)

        chosen_good, reward = engine.resolve_feedback_for_state(fourth_state, "left")
        self.assertFalse(chosen_good)
        self.assertFalse(reward)

    def test_rl_agent_updates_q_values(self) -> None:
        agent = RescorlaWagnerAgent(learning_rate=0.5, inverse_temperature=2.0, initial_q=0.5)
        prediction_error = agent.update("left", True)
        self.assertAlmostEqual(prediction_error, 0.5)
        self.assertAlmostEqual(agent.q_values["left"], 0.75)
        self.assertGreater(agent.choice_probability_left(), 0.5)

    def test_prl_expectedness_and_phase_helpers(self) -> None:
        state_early = PRLTrialState(block=2, trial_index=41, trial_in_block=1, good_side="right", is_reversal_boundary=True)
        state_relearning = PRLTrialState(block=2, trial_index=48, trial_in_block=8, good_side="right", is_reversal_boundary=False)
        state_stable_pre = PRLTrialState(block=2, trial_index=79, trial_in_block=39, good_side="right", is_reversal_boundary=False)

        self.assertEqual(classify_prl_expectedness(True, True), "expected_reward")
        self.assertEqual(classify_prl_expectedness(True, False), "unexpected_no_reward")
        self.assertEqual(classify_prl_expectedness(False, True), "unexpected_reward")
        self.assertEqual(classify_prl_expectedness(False, False), "expected_no_reward")

        self.assertEqual(
            classify_prl_trial_phase(state_early, total_blocks=4, trials_per_block=40, early_post_reversal_trials=5, relearning_trials=10, stable_pre_reversal_trials=5),
            "early_post_reversal",
        )
        self.assertEqual(
            classify_prl_trial_phase(state_relearning, total_blocks=4, trials_per_block=40, early_post_reversal_trials=5, relearning_trials=10, stable_pre_reversal_trials=5),
            "relearning",
        )
        self.assertEqual(
            classify_prl_trial_phase(state_stable_pre, total_blocks=4, trials_per_block=40, early_post_reversal_trials=5, relearning_trials=10, stable_pre_reversal_trials=5),
            "stable_pre_reversal",
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
        config = RDMTaskConfig(blocks=2, trials_per_condition=2, coherence_levels=[0.1, 0.3], directions=("left", "right"))
        trials = build_rdm_trials(config, random.Random(99))

        self.assertEqual(len(trials), 8)
        conditions = {(trial.direction, trial.coherence) for trial in trials}
        self.assertEqual(conditions, {("left", 0.1), ("left", 0.3), ("right", 0.1), ("right", 0.3)})

    def test_rdm_export_helpers_write_files(self) -> None:
        rows = [
            {"trial_index": 1, "coherence": 0.1, "direction": "left", "response": "left", "correct": True, "rt": 0.4, "timeout": False, "response_locked_rt": 0.4, "cpp_slope_proxy": 0.25, "exclude_trial": None},
            {"trial_index": 2, "coherence": 0.1, "direction": "right", "response": "left", "correct": False, "rt": 0.6, "timeout": False, "response_locked_rt": 0.6, "cpp_slope_proxy": 0.166, "exclude_trial": None},
        ]
        with tempfile.TemporaryDirectory() as tmp_dir:
            psychometric_path = Path(tmp_dir) / "psychometric.csv"
            ddm_path = Path(tmp_dir) / "ddm.csv"
            RDMTask.export_psychometric_summary(rows, psychometric_path)
            RDMTask.export_ddm_ready_table(rows, ddm_path)
            self.assertTrue(psychometric_path.exists())
            self.assertTrue(ddm_path.exists())

    def test_rdm_feedback_plan_and_quality_flags(self) -> None:
        self.assertEqual(resolve_rdm_feedback_plan(correct=True, timeout=False, feedback_mode="correctness"), ("correct", "feedback.correct", "正确"))
        self.assertEqual(resolve_rdm_feedback_plan(correct=False, timeout=True, feedback_mode="correctness"), ("timeout", "feedback.timeout", "反应过慢"))
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
