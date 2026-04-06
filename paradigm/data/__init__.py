import importlib

_EXPORTS = {
    "EVENT_FIELDS": ("paradigm.data.logging", "EVENT_FIELDS"),
    "INVALID_NUMERIC": ("paradigm.data.logging", "INVALID_NUMERIC"),
    "TRIAL_FIELDS": ("paradigm.data.logging", "TRIAL_FIELDS"),
    "EventLogger": ("paradigm.data.logging", "EventLogger"),
    "TrialLogger": ("paradigm.data.logging", "TrialLogger"),
    "write_frame_intervals": ("paradigm.data.logging", "write_frame_intervals"),
    "write_metadata": ("paradigm.data.logging", "write_metadata"),
    "build_bids_beh_rows": ("paradigm.data.bids", "build_bids_beh_rows"),
    "build_bids_event_rows": ("paradigm.data.bids", "build_bids_event_rows"),
    "export_run_to_bids": ("paradigm.data.bids", "export_run_to_bids"),
    "discover_run_dirs": ("paradigm.data.normalize", "discover_run_dirs"),
    "normalize_run_dir": ("paradigm.data.normalize", "normalize_run_dir"),
    "expand_trial_rows": ("paradigm.data.run_io", "expand_trial_rows"),
    "load_run_payload": ("paradigm.data.run_io", "load_run_payload"),
    "parse_json_field": ("paradigm.data.run_io", "parse_json_field"),
    "read_csv_rows": ("paradigm.data.run_io", "read_csv_rows"),
    "read_json": ("paradigm.data.run_io", "read_json"),
    "to_bool": ("paradigm.data.run_io", "to_bool"),
    "to_float": ("paradigm.data.run_io", "to_float"),
    "to_int": ("paradigm.data.run_io", "to_int"),
    "export_ddm_ready_table": ("paradigm.data.rdm_export", "export_ddm_ready_table"),
    "export_psychometric_summary": ("paradigm.data.rdm_export", "export_psychometric_summary"),
    "load_normalized_rdm_rows": ("paradigm.data.rdm_export", "load_normalized_rdm_rows"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attr_name = target
    module = importlib.import_module(module_name)
    return getattr(module, attr_name)