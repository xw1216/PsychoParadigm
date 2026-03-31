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
        "gain_trials": {
            "type": "integer",
            "description": "Count of non-timeout trials with displayed gain feedback.",
        },
        "loss_trials": {
            "type": "integer",
            "description": "Count of non-timeout trials with displayed loss feedback.",
        },
        "timeout_trials": {
            "type": "integer",
            "description": "Count of timeout or miss trials with timeout-specific feedback semantics.",
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
        "high_probability_choice_rate": {
            "type": "float",
            "description": "Choice rate for the currently high-probability option among non-timeout trials.",
        },
        "early_post_reversal_choice_rate": {
            "type": "float",
            "description": "Choice rate for the good option during early_post_reversal trials.",
        },
        "late_stable_choice_rate": {
            "type": "float",
            "description": "Choice rate for the good option during late_stable and stable_pre_reversal trials.",
        },
        "expected_reward_count": {
            "type": "integer",
            "description": "Count of trials whose outcome_expectedness equals expected_reward.",
        },
        "unexpected_reward_count": {
            "type": "integer",
            "description": "Count of trials whose outcome_expectedness equals unexpected_reward.",
        },
        "task_positioning": {
            "type": "string",
            "description": "Short human-readable positioning string for PRL pilot/QC interpretation.",
        },
    },
    "rdm": {
        "feedback_mode": {
            "type": "string",
            "description": "Feedback policy active for the run, for example correctness or none.",
        },
        "accuracy_by_coherence": {
            "type": "object",
            "key_type": "stringified coherence",
            "value_type": "float",
            "description": "Accuracy summary keyed by coherence level after trial exclusions used by the task summary logic.",
        },
        "mean_rt_by_coherence": {
            "type": "object",
            "key_type": "stringified coherence",
            "value_type": "float",
            "description": "Mean RT summary keyed by coherence level after trial exclusions used by the task summary logic.",
        },
        "analysis_positioning": {
            "type": "string",
            "description": "Short human-readable positioning string for downstream modeling and QC.",
        },
        "practice_staircase_enabled": {
            "type": "boolean",
            "description": "Whether the current run had practice staircase logic enabled.",
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
        "exclude_trial": {"type": "boolean", "description": "Whether the trial should be excluded from downstream analysis."},
        "exclude_reason": {"type": "string", "description": "Reason for excluding the trial when applicable."},
        "invalid_response": {"type": "boolean", "description": "Whether the trial ended with an invalid or missing behavioral response."},
    },
    "prl": {
        "good_side": {"type": "string", "description": "Current contingency side with higher reward probability."},
        "reward": {"type": "boolean", "description": "Whether reward was delivered on the trial."},
        "chosen_good": {
            "type": "boolean",
            "description": "Primary analysis field: whether the participant chose the currently good side. Retained in task_specific_data to avoid widening shared trial_summary columns.",
            "analysis_role": "primary_analysis_field",
        },
        "trial_in_block": {"type": "integer", "description": "1-based trial index within the current block."},
        "is_reversal_boundary": {"type": "boolean", "description": "Whether the trial begins a new contingency block."},
        "trial_phase": {
            "type": "string",
            "description": "Primary analysis field for PRL phase segmentation, such as early_post_reversal, relearning, late_stable, or stable_pre_reversal. Currently carried via task_specific_data.",
            "analysis_role": "primary_analysis_field",
        },
        "outcome_expectedness": {
            "type": "string",
            "description": "Primary analysis field for outcome-locked analyses, such as expected_reward or unexpected_no_reward. Currently carried via task_specific_data.",
            "analysis_role": "primary_analysis_field",
        },
        "response_event": {"type": "string", "description": "Response-related runtime event_key emitted on the trial."},
        "feedback_event": {"type": "string", "description": "Feedback runtime event_key emitted on the trial."},
        "q_left": {"type": "float", "description": "Rescorla-Wagner Q value for the left option before update."},
        "q_right": {"type": "float", "description": "Rescorla-Wagner Q value for the right option before update."},
        "prediction_error": {
            "type": "float",
            "description": "Primary analysis field: trial-wise prediction error after outcome delivery. Currently carried via task_specific_data.",
            "analysis_role": "primary_analysis_field",
        },
        "choice_probability_left": {"type": "float", "description": "Model-implied left-choice probability before response."},
        "switch_from_previous": {"type": "boolean", "description": "Whether the current choice differs from the previous non-timeout choice."},
        "rl_update_applied": {"type": "boolean", "description": "Whether the trial updated the RL model state."},
        "counted_for_choice_dynamics": {"type": "boolean", "description": "Whether the trial contributes to win-stay/lose-shift style analyses."},
        "timeout_feedback_presented": {"type": "boolean", "description": "Whether timeout feedback was shown on the trial."},
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
        "coherence": {"type": "float", "description": "Motion coherence level presented on the trial."},
        "response_event": {"type": "string", "description": "Response-related runtime event_key emitted on the trial."},
        "feedback_event": {"type": "string", "description": "Correctness feedback runtime event_key emitted on the trial."},
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