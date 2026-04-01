from __future__ import annotations

from typing import Any

from paradigm.config import EyeTrackerConfig, ScreenConfig
from paradigm.hardware.eyetracking.aoi import AOIRegion
from paradigm.hardware.eyetracking.backends import EyeTrackerBackendProtocol, build_eye_tracker_backend


class EyeTrackerManager:
    def __init__(self, config: EyeTrackerConfig, screen_config: ScreenConfig) -> None:
        self.config = config
        self.screen_config = screen_config
        self.backend: EyeTrackerBackendProtocol = build_eye_tracker_backend(config, screen_config)
        self.last_aoi_name: str | None = None

    @property
    def status(self) -> str:
        return self.backend.status

    def poll_gaze_position(self) -> tuple[float, float] | None:
        return self.backend.poll_gaze_position()

    def detect_aoi_transition(self, aoi_regions: list[AOIRegion]) -> dict[str, Any] | None:
        gaze = self.poll_gaze_position()
        if gaze is None:
            return None
        x_pos, y_pos = gaze
        current_name = None
        for region in aoi_regions:
            if region.contains(x_pos, y_pos):
                current_name = region.name
                break
        if current_name == self.last_aoi_name:
            return None
        transition = {
            "aoi_from": self.last_aoi_name,
            "aoi_to": current_name,
            "gaze_x": x_pos,
            "gaze_y": y_pos,
        }
        self.last_aoi_name = current_name
        return transition

    def status_snapshot(self) -> dict[str, Any]:
        return {
            "enabled": self.config.enable_iohub,
            "backend": self.backend.backend_name,
            "status": self.backend.status,
            "tracker_name": self.backend.tracker_name,
            "failure_reason": self.backend.failure_reason,
            "record_aoi_events": self.config.record_aoi_events,
        }

    def close(self) -> None:
        self.backend.close()
