import unittest

from paradigm.tasks.marker_test import build_test_marker_sequence


class MarkerTestTaskLogicTests(unittest.TestCase):
    def test_build_test_marker_sequence_covers_full_range(self) -> None:
        sequence = build_test_marker_sequence(1, 255)
        self.assertEqual(sequence[0], 1)
        self.assertEqual(sequence[-1], 255)
        self.assertEqual(len(sequence), 255)

    def test_build_test_marker_sequence_rejects_invalid_bounds(self) -> None:
        with self.assertRaises(ValueError):
            build_test_marker_sequence(0, 10)
        with self.assertRaises(ValueError):
            build_test_marker_sequence(10, 256)
        with self.assertRaises(ValueError):
            build_test_marker_sequence(20, 10)