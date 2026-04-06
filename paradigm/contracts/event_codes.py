from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EventDefinition:
    event_key: str
    event_code: int
    description: str


def _build_task_events(items: list[tuple[str, int, str]]) -> dict[str, EventDefinition]:
    return {
        event_key: EventDefinition(event_key=event_key, event_code=event_code, description=description)
        for event_key, event_code, description in items
    }


EVENT_REGISTRY: dict[str, dict[str, EventDefinition]] = {
    "doors": _build_task_events(
        [
            ("doors.fixation.onset", 11, "Fixation cross onset before door choice."),
            ("doors.choice.onset", 12, "Door choice screen onset."),
            ("doors.response.left", 13, "Left door response registered."),
            ("doors.response.right", 14, "Right door response registered."),
            ("doors.response.timeout", 15, "No response before timeout."),
            ("doors.post_choice_delay.onset", 16, "Post-choice delay onset."),
            ("doors.feedback.gain", 17, "Gain feedback onset."),
            ("doors.feedback.loss", 18, "Loss feedback onset."),
            ("doors.feedback.timeout", 20, "Timeout or miss feedback onset; distinct from gain/loss outcome feedback."),
            ("doors.iti.onset", 19, "Inter-trial interval onset."),
            ("doors.block.start", 21, "Block start."),
            ("doors.block.end", 22, "Block end."),
            ("doors.break.start", 23, "Scheduled break start."),
            ("doors.break.end", 24, "Scheduled break end."),
            ("doors.experiment.start", 25, "Task start."),
            ("doors.experiment.end", 26, "Task end."),
            ("doors.aoi.transition", 27, "AOI transition logged by eye tracking."),
        ],
    ),
    "prl": _build_task_events(
        [
            ("prl.fixation.onset", 31, "Fixation cross onset before choice."),
            ("prl.choice.onset", 32, "Choice screen onset."),
            ("prl.response.left", 33, "Left response registered."),
            ("prl.response.right", 34, "Right response registered."),
            ("prl.response.timeout", 35, "No response before timeout."),
            ("prl.post_choice_delay.onset", 48, "Selected option hold period onset after a valid choice."),
            ("prl.feedback.reward", 36, "Reward feedback onset."),
            ("prl.feedback.no_reward", 37, "No-reward feedback onset."),
            ("prl.iti.onset", 38, "Inter-trial interval onset."),
            ("prl.reversal.boundary", 39, "Hidden contingency reversal boundary after criterion-based learning."),
            ("prl.feedback.timeout", 40, "Timeout feedback onset; no RL update is applied."),
            ("prl.block.start", 41, "Block start."),
            ("prl.block.end", 42, "Block end."),
            ("prl.break.start", 43, "Scheduled break start."),
            ("prl.break.end", 44, "Scheduled break end."),
            ("prl.experiment.start", 45, "Task start."),
            ("prl.experiment.end", 46, "Task end."),
            ("prl.aoi.transition", 47, "AOI transition logged by eye tracking."),
        ],
    ),
    "rdm": _build_task_events(
        [
            ("rdm.fixation.onset", 51, "Fixation cross onset before motion display."),
            ("rdm.premotion.onset", 60, "Zero-coherence premotion onset before coherent evidence appears."),
            ("rdm.motion.onset", 52, "Random dot motion onset."),
            ("rdm.response.left", 53, "Left response registered."),
            ("rdm.response.right", 54, "Right response registered."),
            ("rdm.response.timeout", 55, "No response before timeout."),
            ("rdm.feedback.correct", 56, "Trial-wise correctness feedback onset for a correct response."),
            ("rdm.feedback.error", 57, "Trial-wise correctness feedback onset for an incorrect response."),
            ("rdm.iti.onset", 58, "Inter-trial interval onset."),
            ("rdm.feedback.timeout", 59, "Timeout feedback onset for the feedback-mode RDM variant."),
            ("rdm.post_response_blank.onset", 68, "Post-response blank interval onset before the ITI."),
            ("rdm.aoi.transition", 61, "AOI transition logged by eye tracking."),
            ("rdm.block.start", 62, "Block start."),
            ("rdm.block.end", 63, "Block end."),
            ("rdm.break.start", 64, "Scheduled break start."),
            ("rdm.break.end", 65, "Scheduled break end."),
            ("rdm.experiment.start", 66, "Task start."),
            ("rdm.experiment.end", 67, "Task end."),
        ],
    ),
    "marker_test": _build_task_events(
        [
            ("marker_test.lsl_wait.start", 69, "Automatic wait for an LSL consumer to appear before the raw marker sweep starts."),
            ("marker_test.lsl_wait.end", 70, "Automatic LSL wait completed, either by detecting a consumer or by falling back when detection is unavailable."),
            ("marker_test.sequence.start", 71, "Start of the raw marker sweep sequence."),
            ("marker_test.pulse", 72, "Raw marker pulse event logged for the current 1-255 test code."),
            ("marker_test.sequence.end", 73, "End of the raw marker sweep sequence."),
            ("marker_test.experiment.start", 74, "Task start."),
            ("marker_test.experiment.end", 75, "Task end."),
        ],
    ),
    "system": _build_task_events(
        [
            ("system.safe_exit.requested", 90, "Escape key requested a safe shutdown."),
            ("system.frame.dropped_warning", 91, "Dropped frame warning logged."),
            ("system.startup.failure", 92, "Runtime startup failure logged."),
        ],
    ),
}


def get_event_definition(task: str, event_name: str) -> EventDefinition:
    if event_name in EVENT_REGISTRY.get(task, {}):
        return EVENT_REGISTRY[task][event_name]
    if event_name in EVENT_REGISTRY["system"]:
        return EVENT_REGISTRY["system"][event_name]
    raise KeyError(f"Unknown event '{event_name}' for task '{task}'")


def get_task_code_map(task: str) -> dict[str, int]:
    return {event_key: definition.event_code for event_key, definition in EVENT_REGISTRY[task].items()}


def build_event_codebook_snapshot() -> dict[str, dict[str, dict[str, str | int]]]:
    return {
        task: {
            event_key: {
                "event_code": definition.event_code,
                "description": definition.description,
            }
            for event_key, definition in definitions.items()
        }
        for task, definitions in EVENT_REGISTRY.items()
    }
