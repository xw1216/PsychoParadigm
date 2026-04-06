import unittest
from unittest.mock import Mock, patch

from paradigm import app as app_module
from paradigm.app import load_task_class, prompt_if_missing


class AppPromptTests(unittest.TestCase):
    def test_prompt_if_missing_returns_existing_value(self) -> None:
        self.assertEqual(prompt_if_missing("P123", "Participant ID", "P001"), "P123")

    def test_prompt_if_missing_uses_fallback_on_eof(self) -> None:
        with patch("builtins.input", side_effect=EOFError):
            self.assertEqual(prompt_if_missing(None, "Participant ID", "P001"), "P001")

    def test_prompt_if_missing_uses_typed_value_when_available(self) -> None:
        with patch("builtins.input", return_value="P777"):
            self.assertEqual(prompt_if_missing(None, "Participant ID", "P001"), "P777")

    def test_task_registry_is_lazy(self) -> None:
        self.assertEqual(app_module.TASK_REGISTRY["doors"], ("paradigm.tasks.doors", "DoorsTask"))
        self.assertEqual(app_module.TASK_REGISTRY["marker_test"], ("paradigm.tasks.marker_test", "MarkerTestTask"))

    def test_load_task_class_uses_importlib_lazily(self) -> None:
        fake_module = Mock()
        fake_module.DoorsTask = object()
        with patch("paradigm.app.importlib.import_module", return_value=fake_module) as import_module:
            resolved = load_task_class("doors")

        import_module.assert_called_once_with("paradigm.tasks.doors")
        self.assertIs(resolved, fake_module.DoorsTask)
