from __future__ import annotations

from typing import Any, Protocol

from paradigm.config import EyeTrackerConfig, ScreenConfig


class EyeTrackerBackendProtocol(Protocol):
    backend_name: str
    status: str
    tracker_name: str | None
    failure_reason: str | None

    def poll_gaze_position(self) -> tuple[float, float] | None:
        ...

    def close(self) -> None:
        ...


class NullEyeTrackerBackend:
    def __init__(
        self,
        *,
        status: str = "disabled",
        backend_name: str = "disabled",
        tracker_name: str | None = None,
        failure_reason: str | None = None,
    ) -> None:
        self.backend_name = backend_name
        self.status = status
        self.tracker_name = tracker_name
        self.failure_reason = failure_reason

    def poll_gaze_position(self) -> tuple[float, float] | None:
        return None

    def close(self) -> None:
        return None


def _import_iohub():
    try:
        from psychopy import iohub
    except ImportError:  # pragma: no cover
        return None
    return iohub


class IoHubEyeTrackerBackend:
    def __init__(self, config: EyeTrackerConfig, screen_config: ScreenConfig) -> None:
        del screen_config
        self.backend_name = "iohub"
        self.status = "disabled"
        self.tracker_name = config.tracker_name
        self.failure_reason: str | None = None
        self.iohub_server = None
        self.tracker = None

        if not config.enable_iohub:
            return

        iohub = _import_iohub()
        if iohub is None:
            self.status = "iohub_unavailable"
            self.failure_reason = "psychopy.iohub_unavailable"
            return

        try:
            launch_config: dict[str, Any] = {
                "eyetracker.hw.mouse.EyeTracker": {
                    "name": config.tracker_name,
                    "runtime_settings": config.runtime_settings,
                }
            }
            self.iohub_server = iohub.launchHubServer(**launch_config)
            self.tracker = self.iohub_server.getDevice(config.tracker_name)
            if self.tracker is None:
                self.status = "tracker_unavailable"
                self.failure_reason = "tracker_unavailable"
                return
            self.status = "ready"
        except Exception as exc:  # pragma: no cover
            self.status = f"error:{exc.__class__.__name__}"
            self.failure_reason = f"{exc.__class__.__name__}:{exc}"
            self.iohub_server = None
            self.tracker = None

    def poll_gaze_position(self) -> tuple[float, float] | None:
        if self.tracker is None:
            return None
        try:
            position = self.tracker.getLastGazePosition()
        except Exception:  # pragma: no cover
            return None
        if position is None:
            return None
        return float(position[0]), float(position[1])

    def close(self) -> None:
        if self.iohub_server is not None:
            try:
                self.iohub_server.quit()
            except Exception:
                pass
        self.iohub_server = None
        self.tracker = None


def build_eye_tracker_backend(config: EyeTrackerConfig, screen_config: ScreenConfig) -> EyeTrackerBackendProtocol:
    if not config.enable_iohub:
        return NullEyeTrackerBackend()
    return IoHubEyeTrackerBackend(config, screen_config)
