import random
from dataclasses import dataclass

from paradigm.config import DoorsTaskConfig
from paradigm.utils.randomization import balanced_binary_sequence


@dataclass(slots=True)
class DoorTrial:
    block: int
    trial_index: int
    feedback_type: str


def format_doors_feedback(trial: DoorTrial, task_config: DoorsTaskConfig) -> tuple[str, str, int]:
    feedback_value = task_config.gain_value if trial.feedback_type == "gain" else task_config.loss_value
    color = "lightgreen" if trial.feedback_type == "gain" else "tomato"
    if task_config.feedback_display_mode == "label":
        text = task_config.gain_label if trial.feedback_type == "gain" else task_config.loss_label
    else:
        text = f"{feedback_value:+d}"
    return text, color, feedback_value


def build_doors_trials(task_config: DoorsTaskConfig, rng: random.Random) -> list[DoorTrial]:
    total_trials = task_config.blocks * task_config.trials_per_block
    sequence = balanced_binary_sequence(total_trials, rng)
    trials: list[DoorTrial] = []
    for block in range(1, task_config.blocks + 1):
        for trial_in_block in range(1, task_config.trials_per_block + 1):
            global_index = (block - 1) * task_config.trials_per_block + trial_in_block
            feedback_type = "gain" if sequence[global_index - 1] == 1 else "loss"
            trials.append(DoorTrial(block=block, trial_index=global_index, feedback_type=feedback_type))
    return trials
