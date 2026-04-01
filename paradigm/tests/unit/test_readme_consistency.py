import unittest
from pathlib import Path


class ReadmeConsistencyTests(unittest.TestCase):
    def test_readme_mentions_marker_fields_and_backend_flag(self) -> None:
        readme = Path("README.md").read_text(encoding="utf-8")
        self.assertIn("event_key", readme)
        self.assertIn("event_code", readme)
        self.assertIn("event_keys", readme)
        self.assertIn("--lpt-backend", readme)

    def test_readme_mentions_output_contracts(self) -> None:
        readme = Path("README.md").read_text(encoding="utf-8")
        self.assertIn("run_summary_schema", readme)
        self.assertIn("run_metadata.json", readme)
        self.assertIn("event_log.csv", readme)
        self.assertIn("trial_summary.csv", readme)

    def test_readme_clarifies_event_code_meaning(self) -> None:
        readme = Path("README.md").read_text(encoding="utf-8")
        self.assertIn("单字节硬件 marker code", readme)

    def test_readme_points_to_docs(self) -> None:
        readme = Path("README.md").read_text(encoding="utf-8")
        self.assertIn("docs/architecture.md", readme)
        self.assertIn("docs/hardware-lpt.md", readme)

    def test_docs_cover_new_package_layout(self) -> None:
        architecture = Path("docs/architecture.md").read_text(encoding="utf-8")
        hardware = Path("docs/hardware-lpt.md").read_text(encoding="utf-8")
        self.assertIn("paradigm.contracts", architecture)
        self.assertIn("paradigm.data", architecture)
        self.assertIn("paradigm.hardware.markers", architecture)
        self.assertIn("InpOutLPTBackend", hardware)
        self.assertIn("PsychoPyParallelLPTBackend", hardware)

    def test_readme_mentions_tools_and_logging_boundary(self) -> None:
        readme = Path("README.md").read_text(encoding="utf-8")
        self.assertIn("paradigm.tools", readme)
        self.assertIn("paradigm.tools.normalize_logs", readme)
        self.assertIn("paradigm.tools.viewer.xdf_viewer", readme)
        self.assertIn("paradigm.tools.export.export_bids", readme)
