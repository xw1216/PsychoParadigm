import unittest
from pathlib import Path


class ReadmeConsistencyTests(unittest.TestCase):
    def test_readme_uses_unified_event_field_names(self) -> None:
        readme = Path("README.md").read_text(encoding="utf-8")
        self.assertIn("event_key", readme)
        self.assertIn("event_code", readme)
        self.assertIn("event_keys", readme)
        self.assertNotIn("hardware_code", readme)

    def test_readme_mentions_run_summary_schema(self) -> None:
        readme = Path("README.md").read_text(encoding="utf-8")
        self.assertIn("run_summary_schema", readme)
        self.assertIn("自动 QC", readme)

    def test_readme_clarifies_event_code_and_quick_qc_boundaries(self) -> None:
        readme = Path("README.md").read_text(encoding="utf-8")
        self.assertIn("单字节硬件 marker code", readme)
        self.assertIn("Quick QC 仅用于现场快速判断运行状态", readme)

    def test_readme_lists_stable_and_reserved_boundaries(self) -> None:
        readme = Path("README.md").read_text(encoding="utf-8")
        self.assertIn("已稳定实现", readme)
        self.assertIn("已预留但未完全封板", readme)

    def test_readme_describes_runtime_and_summary_boundaries(self) -> None:
        readme = Path("README.md").read_text(encoding="utf-8")
        self.assertIn("event_log.csv 的主字段", readme)
        self.assertIn("trial_summary.csv 当前收敛为稳定公共列为主", readme)
        self.assertIn("当前转换重点覆盖行为与事件层，生成的是 BIDS-ready artifacts，而不是完整 BIDS 原始数据集", readme)

    def test_readme_mentions_top_level_tools_and_optional_psychopy_log(self) -> None:
        readme = Path("README.md").read_text(encoding="utf-8")
        self.assertIn("tools/", readme)
        self.assertIn("psychopy.log 默认不再输出", readme)