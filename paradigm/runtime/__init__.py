__all__ = ["AOIRegion", "BaseExperiment", "EyeTrackerManager", "MarkerManager", "MarkerResult", "SafeExitRequested"]


def __getattr__(name: str):
	if name in {"BaseExperiment", "SafeExitRequested"}:
		from .base_experiment import BaseExperiment, SafeExitRequested

		return {"BaseExperiment": BaseExperiment, "SafeExitRequested": SafeExitRequested}[name]
	if name in {"AOIRegion", "EyeTrackerManager"}:
		from .eye_tracking import AOIRegion, EyeTrackerManager

		return {"AOIRegion": AOIRegion, "EyeTrackerManager": EyeTrackerManager}[name]
	if name in {"MarkerManager", "MarkerResult"}:
		from .markers import MarkerManager, MarkerResult

		return {"MarkerManager": MarkerManager, "MarkerResult": MarkerResult}[name]
	raise AttributeError(name)
