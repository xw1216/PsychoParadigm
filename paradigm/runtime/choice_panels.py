from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from paradigm.hardware.eyetracking import AOIRegion


@dataclass(slots=True)
class ChoicePanelStyle:
    left_pos: tuple[float, float] = (-0.25, 0.0)
    right_pos: tuple[float, float] = (0.25, 0.0)
    width: float = 0.22
    height: float = 0.28
    line_width: float = 3.0
    line_color: str = "white"
    idle_fill_color: str = "dimgrey"
    selected_fill_color: str = "darkgreen"
    selected_line_color: str = "lightgreen"
    label_height: float = 0.06
    label_color: str = "white"
    label_gap: float = 0.05
    aoi_padding_x: float = 0.02
    aoi_padding_y: float = 0.02


class ChoicePanelPair:
    def __init__(self, visual: Any, window: Any, *, left_label: str, right_label: str, text_font: str, style: ChoicePanelStyle | None = None) -> None:
        self.style = style or ChoicePanelStyle()
        left_label_pos = self._label_pos(self.style.left_pos)
        right_label_pos = self._label_pos(self.style.right_pos)
        self.left_panel = visual.Rect(
            window,
            width=self.style.width,
            height=self.style.height,
            pos=self.style.left_pos,
            lineColor=self.style.line_color,
            fillColor=self.style.idle_fill_color,
            lineWidth=self.style.line_width,
        )
        self.right_panel = visual.Rect(
            window,
            width=self.style.width,
            height=self.style.height,
            pos=self.style.right_pos,
            lineColor=self.style.line_color,
            fillColor=self.style.idle_fill_color,
            lineWidth=self.style.line_width,
        )
        self.left_text = visual.TextStim(
            window,
            text=left_label,
            pos=left_label_pos,
            height=self.style.label_height,
            color=self.style.label_color,
            font=text_font,
        )
        self.right_text = visual.TextStim(
            window,
            text=right_label,
            pos=right_label_pos,
            height=self.style.label_height,
            color=self.style.label_color,
            font=text_font,
        )

    def _label_pos(self, panel_pos: tuple[float, float]) -> tuple[float, float]:
        return (panel_pos[0], panel_pos[1] - (self.style.height / 2) - self.style.label_gap)

    def set_labels(self, *, left_label: str, right_label: str) -> None:
        self.left_text.text = left_label
        self.right_text.text = right_label

    def draw(self, *, selected: str | None = None) -> None:
        left_selected = selected == "left"
        right_selected = selected == "right"
        self.left_panel.fillColor = self.style.selected_fill_color if left_selected else self.style.idle_fill_color
        self.right_panel.fillColor = self.style.selected_fill_color if right_selected else self.style.idle_fill_color
        self.left_panel.lineColor = self.style.selected_line_color if left_selected else self.style.line_color
        self.right_panel.lineColor = self.style.selected_line_color if right_selected else self.style.line_color
        self.left_panel.draw()
        self.right_panel.draw()
        self.left_text.draw()
        self.right_text.draw()

    def build_aois(self, *, left_name: str, right_name: str) -> list[AOIRegion]:
        return [
            AOIRegion(
                name=left_name,
                left=self.style.left_pos[0] - (self.style.width / 2) - self.style.aoi_padding_x,
                right=self.style.left_pos[0] + (self.style.width / 2) + self.style.aoi_padding_x,
                bottom=self.style.left_pos[1] - (self.style.height / 2) - self.style.aoi_padding_y,
                top=self.style.left_pos[1] + (self.style.height / 2) + self.style.aoi_padding_y,
            ),
            AOIRegion(
                name=right_name,
                left=self.style.right_pos[0] - (self.style.width / 2) - self.style.aoi_padding_x,
                right=self.style.right_pos[0] + (self.style.width / 2) + self.style.aoi_padding_x,
                bottom=self.style.right_pos[1] - (self.style.height / 2) - self.style.aoi_padding_y,
                top=self.style.right_pos[1] + (self.style.height / 2) + self.style.aoi_padding_y,
            ),
        ]