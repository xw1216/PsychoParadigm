from dataclasses import dataclass
from typing import Any

try:
    from psychopy import iohub
except ImportError:  # pragma: no cover
    iohub = None

from paradigm.config import EyeTrackerConfig, ScreenConfig


@dataclass(slots=True)
class AOIRegion:
    name: str
    left: float
    right: float
    bottom: float
    top: float

    def contains(self, x_pos: float, y_pos: float) -> bool:
        return self.left <= x_pos <= self.right and self.bottom <= y_pos <= self.top


class EyeTrackerManager:
    def __init__(self, config: EyeTrackerConfig, screen_config: ScreenConfig) -> None:
        self.config = config
        self.screen_config = screen_config
        self.iohub_server = None
        self.tracker = None
        self.status = "disabled"
        self.last_aoi_name: str | None = None

        if not config.enable_iohub:
            return
        if iohub is None:
            self.status = "iohub_unavailable"
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
            self.status = "ready" if self.tracker is not None else "tracker_unavailable"
        except Exception as exc:  # pragma: no cover
            self.status = f"error:{exc.__class__.__name__}"
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

    def close(self) -> None:
        if self.iohub_server is not None:
            try:
                self.iohub_server.quit()
            except Exception:
                pass
        self.iohub_server = None
        self.tracker = None
