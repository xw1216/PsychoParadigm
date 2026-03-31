import argparse
import unittest

from paradigm.app import apply_cli_overrides
from paradigm.config import DEFAULT_CONFIG


class AppConfigOverrideTests(unittest.TestCase):
    def _args(self, **overrides):
        defaults = {
            "enable_lsl": False,
            "disable_lsl": False,
            "enable_lpt": False,
            "disable_lpt": False,
            "enable_iohub": False,
            "disable_iohub": False,
            "windowed": False,
            "practice": False,
        }
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    def test_enable_flags_override_defaults(self) -> None:
        updated = apply_cli_overrides(DEFAULT_CONFIG, self._args(enable_lpt=True, disable_lsl=True, windowed=True))
        self.assertTrue(updated.markers.enable_lpt)
        self.assertFalse(updated.markers.enable_lsl)
        self.assertFalse(updated.screen.fullscr)

    def test_last_effective_flag_combination_is_stable(self) -> None:
        updated = apply_cli_overrides(DEFAULT_CONFIG, self._args(enable_lsl=True, disable_lsl=True, enable_iohub=True, disable_iohub=True))
        self.assertFalse(updated.markers.enable_lsl)
        self.assertFalse(updated.eye_tracker.enable_iohub)

    def test_default_config_is_not_mutated(self) -> None:
        original_lpt = DEFAULT_CONFIG.markers.enable_lpt
        apply_cli_overrides(DEFAULT_CONFIG, self._args(enable_lpt=not original_lpt))
        self.assertEqual(DEFAULT_CONFIG.markers.enable_lpt, original_lpt)

    def test_practice_override_uses_short_task_configuration(self) -> None:
        updated = apply_cli_overrides(DEFAULT_CONFIG, self._args(practice=True), task_name="rdm")
        self.assertTrue(updated.practice.enabled)
        self.assertEqual(updated.rdm.blocks, updated.rdm.practice_blocks)
        self.assertEqual(updated.rdm.trials_per_condition, updated.rdm.practice_trials_per_condition)
        self.assertEqual(updated.rdm.coherence_levels, updated.rdm.practice_coherence_levels)
        self.assertEqual(updated.common.break_every_n_trials, 9999)
