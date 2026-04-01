from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from paradigm.contracts import get_task_code_map


@dataclass(slots=True)
class ScreenConfig:
    size: tuple[int, int] = (1920, 1080)
    fullscr: bool = True
    monitor_name: str = "testMonitor"
    units: str = "height"
    color: tuple[float, float, float] = (-0.85, -0.85, -0.85)
    allow_gui: bool = False
    wait_blank: bool = True
    record_frame_intervals: bool = True
    target_frame_rate: float = 60.0


@dataclass(slots=True)
class DataConfig:
    root_dir: str = "data"
    metadata_name: str = "run_metadata.json"
    event_log_name: str = "event_log.csv"
    trial_log_name: str = "trial_summary.csv"
    frame_interval_name: str = "frame_intervals.csv"


@dataclass(slots=True)
class MarkerConfig:
    enable_lpt: bool = False
    lsl_stream_name: str = "PsychoParadigmMarkers"
    lsl_stream_type: str = "Markers"
    lsl_source_id: str = "psycho-paradigm-marker-source"

    enable_lsl: bool = True
    lpt_backend: str = "auto"
    lpt_address: int = 0x0378
    lpt_driver_dir: str | None = None
    lpt_dll_name: str = "inpoutx64.dll"
    lpt_pulse_width_ms: float = 5.0
    lpt_reset_on_close: bool = True


@dataclass(slots=True)
class FNIRSConfig:
    enable_namespace: bool = True
    prefix: int = 40
    task_offsets: dict[str, int] = field(
        default_factory=lambda: {
            "doors": 0,
            "prl": 20,
            "rdm": 40,
        }
    )


@dataclass(slots=True)
class EyeTrackerConfig:
    enable_iohub: bool = False
    tracker_name: str = "eyetracker"
    sample_rate: int = 200
    record_aoi_events: bool = True
    fixation_distance_threshold: float = 0.05
    runtime_settings: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LoggingConfig:
    flush_every_event: bool = True
    dropped_frame_factor: float = 1.5


@dataclass(slots=True)
class CommonTaskConfig:
    fixation_s: float = 0.5
    response_timeout_s: float = 1.5
    iti_range_s: tuple[float, float] = (0.8, 1.2)
    break_every_n_trials: int = 40
    continue_key: str = "f9"
    force_continue_key: str = "f10"
    refresh_key: str = "f6"


@dataclass(slots=True)
class PracticeConfig:
    enabled: bool = False


@dataclass(slots=True)
class DoorsTaskConfig:
    blocks: int = 2
    trials_per_block: int = 40
    practice_blocks: int = 2
    practice_trials_per_block: int = 5
    fixation_s: float = 0.5
    response_timeout_s: float = 1.5
    post_choice_delay_s: float = 0.5
    feedback_s: float = 1.0
    iti_range_s: tuple[float, float] = (0.8, 1.2)
    gain_value: int = 10
    loss_value: int = -5
    feedback_display_mode: str = "numeric"
    gain_label: str = "奖励"
    loss_label: str = "损失"
    timeout_feedback_text: str = "反应过慢"

    response_keys: tuple[str, str] = ("left", "right")
    marker_codes: dict[str, int] = field(default_factory=lambda: get_task_code_map("doors"))


@dataclass(slots=True)
class PRLTaskConfig:
    blocks: int = 6
    trials_per_block: int = 24
    practice_blocks: int = 2
    practice_trials_per_block: int = 5
    fixation_s: float = 0.5
    response_timeout_s: float = 1.5
    post_choice_delay_range_s: tuple[float, float] = (0.3, 0.5)
    feedback_s: float = 0.8
    iti_range_s: tuple[float, float] = (0.8, 1.2)
    reward_probability_good: float = 0.75
    reward_probability_bad: float = 0.25
    reward_value: int = 10
    no_reward_value: int = 0
    learning_rate: float = 0.2
    inverse_temperature: float = 4.0
    initial_q: float = 0.5
    early_post_reversal_trials: int = 4
    relearning_trials: int = 8
    stable_pre_reversal_trials: int = 4
    timeout_feedback_text: str = "反应过慢"

    response_keys: tuple[str, str] = ("left", "right")
    marker_codes: dict[str, int] = field(default_factory=lambda: get_task_code_map("prl"))


@dataclass(slots=True)
class RDMTaskConfig:
    blocks: int = 5
    trials_per_condition: int = 10

    fixation_s: float = 0.5
    response_timeout_s: float = 1.5
    post_response_blank_s: float = 0.5
    iti_range_s: tuple[float, float] = (0.8, 1.2)
    feedback_s: float = 0.35

    coherence_levels: list[float] = field(default_factory=lambda: [0.05, 0.1, 0.2, 0.4, 0.6])
    practice_coherence_levels: list[float] = field(default_factory=lambda: [0.1, 0.4, 0.6])
    directions: tuple[str, str] = ("left", "right")
    response_keys: tuple[str, str] = ("left", "right")
    n_dots: int = 250
    field_size: float = 0.6
    dot_life: int = 12
    speed: float = 0.01
    signal_dots: str = "same"
    noise_dots: str = "direction"
    dot_size: float = 4.0
    export_bin_count: int = 5
    feedback_mode: str = "correctness"
    timeout_feedback_text: str = "反应过慢"
    online_fixation_break_detection: bool = False
    exclude_timeouts_from_analysis: bool = True
    confidence_rating_enabled: bool = False

    practice_blocks: int = 2
    practice_trials_per_condition: int = 1
    practice_staircase_enabled: bool = False
    practice_staircase_start_coherence: float = 0.4
    practice_staircase_step: float = 0.05
    practice_staircase_min_coherence: float = 0.05
    practice_staircase_max_coherence: float = 0.8

    marker_codes: dict[str, int] = field(default_factory=lambda: get_task_code_map("rdm"))


@dataclass(slots=True)
class AppConfig:
    screen: ScreenConfig = field(default_factory=ScreenConfig)
    data: DataConfig = field(default_factory=DataConfig)
    markers: MarkerConfig = field(default_factory=MarkerConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    common: CommonTaskConfig = field(default_factory=CommonTaskConfig)
    practice: PracticeConfig = field(default_factory=PracticeConfig)

    fnirs: FNIRSConfig = field(default_factory=FNIRSConfig)
    eye_tracker: EyeTrackerConfig = field(default_factory=EyeTrackerConfig)
    
    doors: DoorsTaskConfig = field(default_factory=DoorsTaskConfig)
    prl: PRLTaskConfig = field(default_factory=PRLTaskConfig)
    rdm: RDMTaskConfig = field(default_factory=RDMTaskConfig)

    def snapshot(self) -> dict[str, Any]:
        return asdict(self)

    def data_root(self) -> Path:
        return Path(self.data.root_dir)


DEFAULT_CONFIG = AppConfig()
