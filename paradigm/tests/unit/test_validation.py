import unittest

from paradigm.runtime.validation import validate_event_trial_consistency, validate_trial_temporal_consistency


class ValidationTests(unittest.TestCase):
    def test_trial_temporal_consistency_accepts_valid_row(self) -> None:
        errors = validate_trial_temporal_consistency({"stim_onset": 1.0, "response_time_abs": 1.4, "feedback_onset": 1.8, "timeout": False, "response": "left"})
        self.assertEqual(errors, [])

    def test_trial_temporal_consistency_flags_invalid_order(self) -> None:
        errors = validate_trial_temporal_consistency({"stim_onset": 2.0, "response_time_abs": 1.5, "feedback_onset": 1.4, "timeout": False, "response": "left"})
        self.assertGreaterEqual(len(errors), 2)

    def test_event_trial_consistency_checks_event_codes(self) -> None:
        event_rows = [
            {"task": "doors", "trial": 1, "event_code": 12},
            {"task": "doors", "trial": 1, "event_code": 16},
            {"task": "doors", "trial": 1, "event_code": 17},
        ]
        trial_rows = [{"task": "doors", "trial_index": 1, "lsl_marker_codes": [12, 16, 17]}]
        self.assertEqual(validate_event_trial_consistency(event_rows, trial_rows), [])

    def test_event_trial_consistency_flags_missing_trial_event(self) -> None:
        event_rows = [{"task": "doors", "trial": 1, "event_code": 12}]
        trial_rows = [{"task": "doors", "trial_index": 2, "lsl_marker_codes": [12]}]
        self.assertTrue(validate_event_trial_consistency(event_rows, trial_rows))
