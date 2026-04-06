from __future__ import annotations

from copy import deepcopy


EVENT_CODEBOOK_SCHEMA: dict[str, object] = {
    "type": "object",
    "description": "Runtime event registry keyed first by task name and then by semantic event_key.",
    "task_key_type": "task_name",
    "event_key_type": "semantic dotted string",
    "event_code_definition": "Single-byte hardware marker code used for runtime transport and logging over LSL/LPT; event semantics remain defined by event_key, not by event_code alone.",
    "constraints": {
        "event_code_range": "0-255",
        "event_code_uniqueness": "event_code values are globally unique across the registry",
    },
    "entry_fields": {
        "event_code": {
            "type": "integer",
            "range": [0, 255],
            "description": "Single-byte hardware marker code for runtime transport/logging. It is not a standalone logical condition code.",
        },
        "description": {
            "type": "string",
            "description": "Human-readable explanation of the runtime event.",
        },
    },
    "scope": "Only stable runtime events emitted by the experiment loop are included here.",
}


RUN_SUMMARY_SCHEMA: dict[str, dict[str, dict[str, object]]] = {
    "common": {
        "n_trials": {
            "type": "integer",
            "description": "Number of trials completed and written to trial_summary.csv.",
        },
        "timeout_rate": {
            "type": "float",
            "description": "Fraction of trials flagged as timeout, on the range 0-1.",
        },
    },
    "doors": {
        "fast_rt_rate": {
            "type": "float",
            "description": "Fraction of valid-response trials whose RT falls below the fast-response QC threshold.",
        },
        "left_choice_rate": {
            "type": "float",
            "description": "Fraction of valid left-key responses among all valid responses.",
        },
        "feedback_counts": {
            "type": "object",
            "description": "Trial counts for gain, loss, and timeout feedback categories.",
        },
        "block_feedback_balance": {
            "type": "object",
            "description": "Per-block gain/loss/timeout counts used to verify pre-balanced feedback schedules.",
        },
        "block_mean_rt": {
            "type": "object",
            "description": "Per-block mean RT values for fatigue or speed-drift checks.",
        },
        "feedback_event_complete": {
            "type": "boolean",
            "description": "Whether every trial summary row contains at least one doors.feedback.* event_key in event_keys.",
        },
        "task_positioning": {
            "type": "string",
            "description": "Short human-readable positioning string for field QC and downstream interpretation.",
        },
    },
    "prl": {
        "optimal_choice_rate": {
            "type": "float",
            "description": "Choice rate for the currently optimal stimulus among non-timeout trials.",
        },
        "mean_rt": {
            "type": "float",
            "description": "Mean RT across non-timeout trials.",
        },
        "win_stay_rate": {
            "type": "float",
            "description": "Probability of staying with the same stimulus after reward feedback.",
        },
        "lose_shift_rate": {
            "type": "float",
            "description": "Probability of switching stimuli after no-reward feedback.",
        },
        "veridical_win_stay_rate": {
            "type": "float",
            "description": "Win-stay rate restricted to non-misleading reward feedback.",
        },
        "misleading_lose_shift_rate": {
            "type": "float",
            "description": "Lose-shift rate after misleading no-reward feedback on an otherwise optimal choice.",
        },
        "switch_rate": {
            "type": "float",
            "description": "Overall switch rate between chosen stimuli on valid consecutive trials.",
        },
        "mean_trials_to_criterion": {
            "type": "float",
            "description": "Mean number of trials needed to reach the hidden-reversal criterion across contingency segments.",
        },
        "perseverative_error_rate": {
            "type": "float",
            "description": "Error rate during early post-reversal trials, used as a simple perseveration proxy.",
        },
        "regressive_error_rate": {
            "type": "float",
            "description": "Error rate during stable trials after relearning, used as a simple regressive-error proxy.",
        },
        "reversal_curve": {
            "type": "object",
            "description": "Reversal-centered learning curve keyed by trial offset from the latest hidden reversal.",
        },
        "reversal_count": {
            "type": "integer",
            "description": "Number of hidden contingency reversals completed during the run.",
        },
        "task_positioning": {
            "type": "string",
            "description": "Short human-readable positioning string for PRL pilot/QC interpretation.",
        },
    },
    "rdm": {
        "psychometric_right_choice": {
            "type": "object",
            "key_type": "stringified signed coherence",
            "value_type": "float",
            "description": "Psychometric curve summary: P(right choice) as a function of signed coherence.",
        },
        "feedback_mode": {
            "type": "string",
            "description": "Feedback policy active for the run, for example correctness or none.",
        },
        "accuracy_by_abs_coherence": {
            "type": "object",
            "key_type": "stringified absolute coherence",
            "value_type": "float",
            "description": "Accuracy summary keyed by absolute coherence level after trial exclusions.",
        },
        "mean_rt_by_abs_coherence": {
            "type": "object",
            "key_type": "stringified absolute coherence",
            "value_type": "float",
            "description": "Mean RT summary keyed by absolute coherence level after trial exclusions.",
        },
        "correct_mean_rt_by_abs_coherence": {
            "type": "object",
            "key_type": "stringified absolute coherence",
            "value_type": "float",
            "description": "Mean RT for correct trials keyed by absolute coherence level.",
        },
        "error_mean_rt_by_abs_coherence": {
            "type": "object",
            "key_type": "stringified absolute coherence",
            "value_type": "float",
            "description": "Mean RT for error trials keyed by absolute coherence level.",
        },
        "chronometric_signed": {
            "type": "object",
            "key_type": "stringified signed coherence",
            "value_type": "float",
            "description": "Signed-coherence chronometric summary of mean RT values.",
        },
        "analysis_positioning": {
            "type": "string",
            "description": "Short human-readable positioning string for downstream modeling and QC.",
        },
        "practice_staircase_enabled": {
            "type": "boolean",
            "description": "Whether the current run had practice staircase logic enabled.",
        },
        "premotion_s": {
            "type": "float",
            "description": "Duration of the zero-coherence premotion phase in seconds.",
        },
    },
    "marker_test": {
        "first_marker_code": {
            "type": "integer",
            "description": "First raw hardware code requested in the sweep.",
        },
        "last_marker_code": {
            "type": "integer",
            "description": "Last raw hardware code requested in the sweep.",
        },
        "interval_s": {
            "type": "float",
            "description": "Fixed interval between consecutive raw marker sends in seconds.",
        },
        "consumer_detected_at_start": {
            "type": ["boolean", "null"],
            "description": "Whether an LSL consumer was detected before the raw marker sweep started. Null means detection was unavailable.",
        },
        "lsl_markers_sent": {
            "type": "integer",
            "description": "Count of raw marker pulses successfully sent over LSL.",
        },
        "lpt_markers_sent": {
            "type": "integer",
            "description": "Count of raw marker pulses successfully sent over LPT.",
        },
        "task_positioning": {
            "type": "string",
            "description": "Short human-readable positioning string for marker transport validation runs.",
        },
    },
}


TASK_SPECIFIC_DATA_FIELDS: dict[str, dict[str, dict[str, object]]] = {
    "doors": {
        "post_choice_delay_onset": {
            "type": "float",
            "description": "Doors-specific critical phase timestamp for the post-choice delay flip; kept in task_specific_data rather than promoted to a shared trial_summary column.",
            "analysis_role": "task_critical_phase_timestamp",
        },
        "scheduled_feedback_type": {"type": "string", "description": "Nominal trial condition assigned before the response: gain or loss."},
        "feedback_type": {"type": "string", "description": "Displayed feedback category for the trial: gain, loss, or timeout."},
        "feedback_semantics": {"type": "string", "description": "Whether the displayed feedback should be interpreted as a true outcome or as a timeout/miss marker."},
        "feedback_value": {"type": ["integer", "null"], "description": "Configured numeric feedback magnitude shown on the trial when numeric mode is used. Timeout feedback uses null."},
        "feedback_display_mode": {"type": "string", "description": "Presentation mode for feedback, for example numeric or label."},
        "response_event": {"type": "string", "description": "Response-related runtime event_key emitted on the trial."},
        "feedback_event": {"type": "string", "description": "Feedback runtime event_key emitted on the trial."},
        "previous_feedback": {"type": "string", "description": "Previous trial feedback category used for lightweight history covariates."},
        "feedback_run_length": {"type": "integer", "description": "Length of the current gain/loss/timeout streak including the current trial."},
        "block_trial_index": {"type": "integer", "description": "1-based trial position within the current block."},
        "exclude_trial": {"type": "boolean", "description": "Whether the trial should be excluded from downstream analysis."},
        "exclude_reason": {"type": "string", "description": "Reason for excluding the trial when applicable."},
        "invalid_response": {"type": "boolean", "description": "Whether the trial ended with an invalid or missing behavioral response."},
    },
    "prl": {
        "good_stimulus": {"type": "string", "description": "Current stimulus identity with higher reward probability."},
        "chosen_stimulus": {"type": "string", "description": "Stimulus identity chosen on the trial."},
        "unchosen_stimulus": {"type": "string", "description": "Stimulus identity not chosen on the trial."},
        "left_stimulus": {"type": "string", "description": "Stimulus identity displayed on the left side for the current trial."},
        "right_stimulus": {"type": "string", "description": "Stimulus identity displayed on the right side for the current trial."},
        "reward": {"type": "boolean", "description": "Whether reward was delivered on the trial."},
        "optimal_choice": {
            "type": "boolean",
            "description": "Primary analysis field: whether the participant chose the currently optimal stimulus. Retained in task_specific_data to avoid widening shared trial_summary columns.",
            "analysis_role": "primary_analysis_field",
        },
        "misleading_feedback": {"type": "boolean", "description": "Whether the observed feedback contradicts the latent optimality of the chosen stimulus under the probabilistic schedule."},
        "reversal_index": {"type": "integer", "description": "Index of the current contingency segment, incremented after each hidden reversal."},
        "reversal_trial_offset": {"type": "integer", "description": "0-based trial offset from the most recent hidden reversal boundary."},
        "trial_phase": {
            "type": "string",
            "description": "Primary analysis field for PRL phase segmentation, such as initial_learning, early_post_reversal, relearning, or stable. Currently carried via task_specific_data.",
            "analysis_role": "primary_analysis_field",
        },
        "outcome_expectedness": {
            "type": "string",
            "description": "Primary analysis field for outcome-locked analyses, such as expected_reward or unexpected_no_reward. Currently carried via task_specific_data.",
            "analysis_role": "primary_analysis_field",
        },
        "response_event": {"type": "string", "description": "Response-related runtime event_key emitted on the trial."},
        "feedback_event": {"type": "string", "description": "Feedback runtime event_key emitted on the trial."},
        "post_choice_delay_onset": {"type": "float", "description": "Timestamp of the selected-stimulus hold interval before feedback."},
        "stimulus_A_value": {"type": "float", "description": "Current model value estimate for stimulus A before outcome update."},
        "stimulus_B_value": {"type": "float", "description": "Current model value estimate for stimulus B before outcome update."},
        "chosen_value": {"type": "float", "description": "Current model value estimate for the chosen stimulus before outcome update."},
        "unchosen_value": {"type": "float", "description": "Current model value estimate for the unchosen stimulus before outcome update."},
        "signed_prediction_error": {
            "type": "float",
            "description": "Primary analysis field: trial-wise prediction error after outcome delivery. Currently carried via task_specific_data.",
            "analysis_role": "primary_analysis_field",
        },
        "unsigned_prediction_error": {
            "type": "float",
            "description": "Primary analysis field: unsigned surprise signal after outcome delivery. Currently carried via task_specific_data.",
            "analysis_role": "primary_analysis_field",
        },
        "left_choice_probability": {"type": "float", "description": "Model-implied probability of choosing the left-side option under the current layout."},
        "switch_from_previous": {"type": "boolean", "description": "Whether the current chosen stimulus differs from the previous valid chosen stimulus."},
        "previous_feedback": {"type": "string", "description": "Previous valid-trial feedback category used for win-stay/lose-shift analyses."},
        "rl_update_applied": {"type": "boolean", "description": "Whether the trial updated the RL model state."},
        "counted_for_choice_dynamics": {"type": "boolean", "description": "Whether the trial contributes to win-stay/lose-shift style analyses."},
        "timeout_feedback_presented": {"type": "boolean", "description": "Whether timeout feedback was shown on the trial."},
        "criterion_reached": {"type": "boolean", "description": "Whether the current contingency segment met the criterion for triggering a hidden reversal after this trial."},
        "trials_to_criterion": {"type": "integer", "description": "Number of trials required to reach the current contingency criterion when criterion_reached is true."},
        "exclude_trial": {"type": "boolean", "description": "Whether the trial should be excluded from downstream analysis."},
        "exclude_reason": {"type": "string", "description": "Reason for excluding the trial when applicable."},
        "invalid_response": {"type": "boolean", "description": "Whether the trial ended with an invalid or missing behavioral response."},
        "first_fixation_aoi": {"type": "string", "description": "Optional first fixation AOI summary derived from eye-tracking transitions when available."},
        "last_fixation_aoi": {"type": "string", "description": "Optional last fixation AOI summary derived from eye-tracking transitions when available."},
        "dwell_left_s": {"type": "float", "description": "Optional left-option dwell time summary when available."},
        "dwell_right_s": {"type": "float", "description": "Optional right-option dwell time summary when available."},
        "dwell_asymmetry": {"type": "float", "description": "Optional dwell asymmetry summary when available."},
        "exploration_after_reversal": {"type": "float", "description": "Optional exploration summary after reversal when available."},
        "aoi_summary_available": {"type": "boolean", "description": "Whether trial-level AOI summaries were computed online for this trial."},
    },
    "rdm": {
        "direction": {"type": "string", "description": "Ground-truth motion direction for the trial."},
        "signed_coherence": {"type": "float", "description": "Signed coherence level presented on the trial; negative values indicate leftward motion and positive values indicate rightward motion."},
        "absolute_coherence": {"type": "float", "description": "Absolute motion coherence magnitude presented on the trial."},
        "premotion_onset": {"type": "float", "description": "Timestamp of the zero-coherence premotion interval onset."},
        "response_event": {"type": "string", "description": "Response-related runtime event_key emitted on the trial."},
        "feedback_event": {"type": "string", "description": "Correctness feedback runtime event_key emitted on the trial."},
        "post_response_blank_onset": {"type": "float", "description": "Timestamp of the post-response blank interval onset."},
        "feedback_mode": {"type": "string", "description": "Current feedback mode, for example correctness or none."},
        "response_locked_rt": {"type": "float", "description": "Response-locked RT helper field for downstream analysis."},
        "cpp_slope_proxy": {"type": "float", "description": "Simple coherence-over-RT proxy retained for downstream modeling/export."},
        "fixation_break_detected": {
            "type": "boolean",
            "description": "Whether a fixation break was flagged under the current rule set. At present this mainly supports exclusion/annotation semantics, not a fully closed-loop online control path.",
        },
        "fixation_break_online_detection": {
            "type": "boolean",
            "description": "Whether fixation breaks were evaluated online during the task. Default configurations leave this disabled.",
        },
        "exclude_trial": {"type": "boolean", "description": "Analysis exclusion flag retained for downstream processing."},
        "exclude_reason": {"type": "string", "description": "Reason for excluding the trial from downstream analyses, such as fixation_break, invalid_response, or timeout."},
        "invalid_response": {"type": "boolean", "description": "Whether the trial ended with an invalid or missing behavioral response."},
        "confidence_rating_enabled": {"type": "boolean", "description": "Whether a confidence-rating stage is enabled for the current task mode. This currently marks a reserved hook rather than a completed stage implementation."},
    },
    "marker_test": {
        "raw_marker_code": {"type": "integer", "description": "Raw marker code sent on the current trial-like row."},
        "sequence_index": {"type": "integer", "description": "1-based position of the current raw code within the 1-255 sweep."},
        "send_interval_s": {"type": "float", "description": "Configured inter-marker interval in seconds."},
        "marker_label": {"type": "string", "description": "Marker label embedded into the raw LSL payload for the current code."},
    },
}


def build_event_codebook_schema() -> dict[str, object]:
    return deepcopy(EVENT_CODEBOOK_SCHEMA)


def get_task_specific_data_fields(task: str) -> dict[str, dict[str, object]]:
    return deepcopy(TASK_SPECIFIC_DATA_FIELDS.get(task, {}))


def get_task_specific_data_schema(task: str) -> dict[str, object]:
    primary_fields = [
        field_name
        for field_name, field_schema in TASK_SPECIFIC_DATA_FIELDS.get(task, {}).items()
        if field_schema.get("analysis_role") == "primary_analysis_field"
    ]
    return {
        "type": "object",
        "description": "Task-specific extension bucket for fields that are not part of the shared trial_summary columns.",
        "boundary_notes": [
            "Shared trial_summary columns stay intentionally narrow across tasks.",
            "Some task_specific_data fields are still primary analysis variables for a given task and should be treated accordingly downstream.",
        ],
        "primary_analysis_fields": primary_fields,
        "fields": get_task_specific_data_fields(task),
    }


def get_run_summary_schema(task: str) -> dict[str, object]:
    return {
        "type": "object",
        "description": "Task-level quick QC summary written into run_metadata.json for direct downstream consumption.",
        "usage_boundary": "Quick on-site sanity check only; does not replace formal offline preprocessing or quality-control workflows.",
        "common_fields": deepcopy(RUN_SUMMARY_SCHEMA["common"]),
        "task_fields": deepcopy(RUN_SUMMARY_SCHEMA.get(task, {})),
    }
