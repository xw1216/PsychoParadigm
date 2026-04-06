import importlib

from .doors_logic import DoorTrial, build_doors_trials, format_doors_feedback

__all__ = ["DoorTrial", "DoorsTask", "build_doors_trials", "format_doors_feedback"]


def __getattr__(name: str):
	if name == "DoorsTask":
		return getattr(importlib.import_module("paradigm.tasks.doors.doors"), name)
	raise AttributeError(name)