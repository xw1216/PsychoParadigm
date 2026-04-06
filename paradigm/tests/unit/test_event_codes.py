import unittest

from paradigm.contracts import EVENT_REGISTRY, build_event_codebook_schema, build_event_codebook_snapshot, get_event_definition, get_run_summary_schema, get_task_code_map, get_task_specific_data_schema


class EventCodeTests(unittest.TestCase):
    def test_task_code_map_uses_byte_sized_codes(self) -> None:
        code_map = get_task_code_map("doors")
        self.assertEqual(code_map["doors.fixation.onset"], 11)
        self.assertEqual(code_map["doors.choice.onset"], 12)
        self.assertEqual(code_map["doors.feedback.gain"], 17)
        self.assertEqual(code_map["doors.feedback.timeout"], 20)
        self.assertTrue(all(0 <= value <= 255 for value in code_map.values()))

    def test_event_definition_contains_semantic_name(self) -> None:
        definition = get_event_definition("prl", "prl.reversal.boundary")
        self.assertEqual(definition.event_code, 39)
        self.assertEqual(definition.event_key, "prl.reversal.boundary")
        self.assertEqual(definition.description, "Hidden contingency reversal boundary after criterion-based learning.")

    def test_codebook_snapshot_contains_labels_and_metadata(self) -> None:
        snapshot = build_event_codebook_snapshot()
        self.assertIn("rdm", snapshot)
        self.assertEqual(snapshot["rdm"]["rdm.motion.onset"]["event_code"], 52)
        self.assertEqual(snapshot["rdm"]["rdm.motion.onset"]["description"], "Random dot motion onset.")
        self.assertEqual(snapshot["marker_test"]["marker_test.pulse"]["event_code"], 72)

    def test_event_codes_are_globally_unique_and_byte_sized(self) -> None:
        all_codes = [definition.event_code for task_events in EVENT_REGISTRY.values() for definition in task_events.values()]
        self.assertTrue(all(0 <= value <= 255 for value in all_codes))
        self.assertEqual(len(all_codes), len(set(all_codes)))

    def test_task_runtime_event_keys_used_by_tasks_resolve(self) -> None:
        task_event_keys = {
            "doors": [
                "doors.fixation.onset",
                "doors.choice.onset",
                "doors.response.left",
                "doors.response.right",
                "doors.response.timeout",
                "doors.post_choice_delay.onset",
                "doors.feedback.gain",
                "doors.feedback.loss",
                "doors.feedback.timeout",
                "doors.iti.onset",
                "doors.block.start",
                "doors.block.end",
                "doors.experiment.start",
                "doors.experiment.end",
                "doors.aoi.transition",
            ],
            "prl": [
                "prl.fixation.onset",
                "prl.choice.onset",
                "prl.response.left",
                "prl.response.right",
                "prl.response.timeout",
                "prl.post_choice_delay.onset",
                "prl.feedback.reward",
                "prl.feedback.no_reward",
                "prl.feedback.timeout",
                "prl.iti.onset",
                "prl.reversal.boundary",
                "prl.block.start",
                "prl.block.end",
                "prl.experiment.start",
                "prl.experiment.end",
                "prl.aoi.transition",
            ],
            "rdm": [
                "rdm.fixation.onset",
                "rdm.premotion.onset",
                "rdm.motion.onset",
                "rdm.response.left",
                "rdm.response.right",
                "rdm.response.timeout",
                "rdm.feedback.correct",
                "rdm.feedback.error",
                "rdm.feedback.timeout",
                "rdm.post_response_blank.onset",
                "rdm.iti.onset",
                "rdm.block.start",
                "rdm.block.end",
                "rdm.experiment.start",
                "rdm.experiment.end",
                "rdm.aoi.transition",
            ],
            "marker_test": [
                "marker_test.lsl_wait.start",
                "marker_test.lsl_wait.end",
                "marker_test.sequence.start",
                "marker_test.pulse",
                "marker_test.sequence.end",
                "marker_test.experiment.start",
                "marker_test.experiment.end",
            ],
        }
        for task_name, event_keys in task_event_keys.items():
            for event_key in event_keys:
                definition = get_event_definition(task_name, event_key)
                self.assertEqual(definition.event_key, event_key)

    def test_run_summary_schema_exposes_common_and_task_fields(self) -> None:
        schema = get_run_summary_schema("rdm")
        self.assertEqual(schema["type"], "object")
        self.assertIn("Quick on-site sanity check only", schema["usage_boundary"])
        self.assertIn("n_trials", schema["common_fields"])
        self.assertIn("timeout_rate", schema["common_fields"])
        self.assertIn("feedback_mode", schema["task_fields"])
        self.assertIn("accuracy_by_abs_coherence", schema["task_fields"])
        self.assertIn("psychometric_right_choice", schema["task_fields"])

    def test_event_codebook_schema_clarifies_hardware_marker_meaning(self) -> None:
        schema = build_event_codebook_schema()
        self.assertIn("Single-byte hardware marker code", schema["event_code_definition"])
        self.assertIn("not a standalone logical condition code", schema["entry_fields"]["event_code"]["description"])

    def test_task_specific_data_schema_marks_primary_prl_analysis_fields(self) -> None:
        schema = get_task_specific_data_schema("prl")
        self.assertIn("optimal_choice", schema["primary_analysis_fields"])
        self.assertIn("trial_phase", schema["primary_analysis_fields"])
        self.assertIn("outcome_expectedness", schema["primary_analysis_fields"])
        self.assertIn("signed_prediction_error", schema["primary_analysis_fields"])
        self.assertIn("unsigned_prediction_error", schema["primary_analysis_fields"])
