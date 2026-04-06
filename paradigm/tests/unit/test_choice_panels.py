import unittest

from paradigm.runtime.choice_panels import ChoicePanelPair, ChoicePanelStyle


class FakeRect:
    def __init__(self, window, width, height, pos, lineColor, fillColor, lineWidth) -> None:
        self.window = window
        self.width = width
        self.height = height
        self.pos = pos
        self.lineColor = lineColor
        self.fillColor = fillColor
        self.lineWidth = lineWidth
        self.draw_count = 0

    def draw(self) -> None:
        self.draw_count += 1


class FakeTextStim:
    def __init__(self, window, text, pos, height, color, font) -> None:
        self.window = window
        self.text = text
        self.pos = pos
        self.height = height
        self.color = color
        self.font = font
        self.draw_count = 0

    def draw(self) -> None:
        self.draw_count += 1


class FakeVisual:
    Rect = FakeRect
    TextStim = FakeTextStim


class ChoicePanelsTests(unittest.TestCase):
    def test_build_aois_matches_panel_geometry(self) -> None:
        style = ChoicePanelStyle(width=0.22, height=0.28, aoi_padding_x=0.02, aoi_padding_y=0.02)
        panels = ChoicePanelPair(FakeVisual, object(), left_label="左", right_label="右", text_font="Microsoft YaHei", style=style)

        left_aoi, right_aoi = panels.build_aois(left_name="left", right_name="right")

        self.assertAlmostEqual(left_aoi.left, -0.38)
        self.assertAlmostEqual(left_aoi.right, -0.12)
        self.assertAlmostEqual(left_aoi.bottom, -0.16)
        self.assertAlmostEqual(left_aoi.top, 0.16)
        self.assertAlmostEqual(right_aoi.left, 0.12)
        self.assertAlmostEqual(right_aoi.right, 0.38)

    def test_draw_updates_selected_panel_state(self) -> None:
        panels = ChoicePanelPair(FakeVisual, object(), left_label="A", right_label="B", text_font="Microsoft YaHei")

        panels.draw(selected="left")

        self.assertEqual(panels.left_panel.fillColor, panels.style.selected_fill_color)
        self.assertEqual(panels.left_panel.lineColor, panels.style.selected_line_color)
        self.assertEqual(panels.right_panel.fillColor, panels.style.idle_fill_color)
        self.assertEqual(panels.left_text.draw_count, 1)
        self.assertEqual(panels.right_text.draw_count, 1)