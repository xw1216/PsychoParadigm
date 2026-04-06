import unittest

from paradigm.utils.fonts import choose_text_font, is_unexpected_cjk_variant


class FontResolutionTests(unittest.TestCase):
    def test_detects_unexpected_cjk_variant(self) -> None:
        self.assertTrue(is_unexpected_cjk_variant("Noto Sans CJK SC", "Noto Sans CJK JP"))
        self.assertFalse(is_unexpected_cjk_variant("AR PL UMing CN", "AR PL UMing CN"))

    def test_choose_text_font_prefers_windows_sans_font_when_available(self) -> None:
        resolved = {
            "Microsoft YaHei UI": "Microsoft YaHei",
            "Microsoft YaHei": "Microsoft YaHei",
            "Droid Sans Fallback": "Droid Sans Fallback",
        }

        request, runtime_name = choose_text_font(
            fallback_fonts=("Microsoft YaHei UI", "Microsoft YaHei", "Droid Sans Fallback"),
            font_loader=resolved.get,
        )

        self.assertEqual(request, "Microsoft YaHei UI")
        self.assertEqual(runtime_name, "Microsoft YaHei")

    def test_choose_text_font_skips_japanese_variant_for_simplified_chinese_request(self) -> None:
        resolved = {
            "Microsoft YaHei UI": None,
            "Microsoft YaHei": None,
            "Noto Sans CJK SC": "Noto Sans CJK JP",
            "WenQuanYi Zen Hei": "Noto Sans CJK JP",
            "Droid Sans Fallback": "Droid Sans Fallback",
        }

        request, runtime_name = choose_text_font(
            fallback_fonts=("Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC", "WenQuanYi Zen Hei", "Droid Sans Fallback"),
            font_loader=resolved.get,
        )

        self.assertEqual(request, "Droid Sans Fallback")
        self.assertEqual(runtime_name, "Droid Sans Fallback")

    def test_choose_text_font_falls_back_to_backend_default_when_no_candidate_works(self) -> None:
        resolved = {
            "Unknown Font": None,
            "": "Noto Sans CJK JP",
        }

        request, runtime_name = choose_text_font(
            fallback_fonts=("Unknown Font",),
            font_loader=resolved.get,
        )

        self.assertEqual(request, "")
        self.assertEqual(runtime_name, "Noto Sans CJK JP")