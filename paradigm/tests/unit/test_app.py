import unittest
from unittest.mock import patch

from paradigm.app import prompt_if_missing


class AppPromptTests(unittest.TestCase):
    def test_prompt_if_missing_returns_existing_value(self) -> None:
        self.assertEqual(prompt_if_missing("P123", "Participant ID", "P001"), "P123")

    def test_prompt_if_missing_uses_fallback_on_eof(self) -> None:
        with patch("builtins.input", side_effect=EOFError):
            self.assertEqual(prompt_if_missing(None, "Participant ID", "P001"), "P001")

    def test_prompt_if_missing_uses_typed_value_when_available(self) -> None:
        with patch("builtins.input", return_value="P777"):
            self.assertEqual(prompt_if_missing(None, "Participant ID", "P001"), "P777")