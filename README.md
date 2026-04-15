# PsychoParadigm

一个面向 EEG / LSL / LPT marker / eye tracking 扩展的 PsychoPy 实验项目骨架。当前内置 `doors`、`prl`、`rdm` 以及 `marker_test` 任务，并保留统一的事件码、日志、导出与硬件 marker 管线。

更详细的结构说明见 [docs/architecture.md](docs/architecture.md)，LPT 后端说明见 [docs/hardware-lpt.md](docs/hardware-lpt.md)。

项目根目录包含 `lsl_api.cfg`，默认关闭 IPv6 并把 resolve scope 限制在 link-local，用于降低多网卡环境下 liblsl multicast responder 的端口占用告警；如果实验机已有独立配置，也可以通过环境变量 `LSLAPICFG` 或 `MarkerConfig.lsl_api_config` 覆盖。

## Quick Start

默认推荐：

```bash
uv run python main.py doors --participant P001 --session S01 --windowed
uv run python main.py prl --participant P001 --session S01 --windowed
uv run python main.py rdm --participant P001 --session S01 --windowed
uv run python main.py marker_test --participant P001 --session S01 --windowed --enable-lsl
```

如果本机维护了 `conda` 环境 `psycho`，可以等价改用：

```bash
conda run -n psycho python main.py doors --participant P001 --session S01 --windowed
```

## Marker Options

启用 LPT：

```bash
uv run python main.py doors --participant P001 --session S01 --enable-lpt
```

显式选择 LPT backend：

```bash
uv run python main.py doors --participant P001 --session S01 --enable-lpt --lpt-backend auto
uv run python main.py doors --participant P001 --session S01 --enable-lpt --lpt-backend inpout
uv run python main.py doors --participant P001 --session S01 --enable-lpt --lpt-backend psychopy
```

说明：

- `auto` 会先尝试 Windows `inpout`，失败后回退到 PsychoPy parallel。
- `inpout` 适合 Windows 实验机上的正式 LPT 输出。
- `psychopy` 适合已有 parallel 驱动链路的环境。
- runtime LSL marker 流现在发送单通道 `int32` `event_code`，不再把 JSON/fNIRS namespace 混发到同一条 stream；详细语义仍以 `event_log.csv` / `trial_summary.csv` 为准。
- runtime 里统一使用 `event_key`、`event_code`、`event_keys`；其中 `event_code` 是单字节硬件 marker code。

禁用 LSL：

```bash
uv run python main.py doors --participant P001 --session S01 --disable-lsl
```

启用 ioHub：

```bash
uv run python main.py doors --enable-iohub
```

## Output

每次运行输出到：

```text
data/sub-<participant>/ses-<session>/<task>/<timestamp>/
```

核心文件：

- `run_metadata.json`
- `event_log.csv`
- `trial_summary.csv`
- `frame_intervals.csv`
- `log_audit.json`（practice 运行后自动生成）

其中：

- `event_log.csv` 是逐事件真源。
- `trial_summary.csv` 是逐 trial 汇总，阶段时间字段统一使用同一套 global_clock 秒数基准。
- `event_log.csv` 中 `abs_time` 与 `flip_time` 现在使用同一套 global_clock 秒数基准，适合直接和 `trial_summary.csv` 的阶段时间字段对齐；`task_time` 保持为相对任务开始的秒数。
- `fnirs_marker_codes` 现在仅保留为可选的离线命名空间映射字段，不再通过 runtime LSL marker stream 传输。
- `run_metadata.json` 会记录 `run_summary_schema`、marker backend 状态和配置快照。
- `log_audit.json` 会对 practice run 自动检查事件完整性、阶段时长、掉帧和 marker 语义。

## Package Layout

当前主结构：

- `paradigm.contracts`: 事件码、schema、validation
- `paradigm.data`: 日志写出、BIDS 导出、run payload 读取、normalize、面向工具层的数据适配
- `paradigm.analysis`: 纯分析汇总与离线表格导出
- `paradigm.hardware.markers`: marker manager 与 LPT backend
- `paradigm.runtime`: 实验生命周期与 runtime session
- `paradigm.tasks`: 任务包
- `paradigm.tasks.<task>.<task>_logic`: 可在 headless 环境导入的纯逻辑层
- `paradigm.tools`: 包内工具实现

## Task Protocols

- `doors`: 每个 block 内强制平衡 gain/loss 反馈序列；trial_summary 会额外记录 `previous_feedback`、`feedback_run_length`、`block_trial_index` 等轻量历史协变量，便于做反馈锁定 QC 与回归分析。
- `prl`: 使用固定刺激身份，但屏幕只显示左右箭头，不显示 A/B；奖励遵循 80/20 contingency，只有背后的高概率刺激会在学习准则触发后隐藏反转；trial_summary 会记录 `optimal_choice`、`trial_phase`、`outcome_expectedness`、signed/unsigned prediction error 等分析字段。
- `rdm`: 使用 signed coherence 条件，0% premotion phase 与显式 `post_response_blank` 事件；行为汇总按 absolute coherence 聚合，同时保留 psychometric、chronometric 和 DDM-ready 离线表。
- `marker_test`: 自动等待 LSL 订阅端后，以固定间隔顺序发送 1 到 255 的原始 marker code，用于纯传输链路验证，不需要任何行为按键。

## Tools

工具入口：

```bash
uv run python -m paradigm.tools.viewer.lsl_monitor
uv run python -m paradigm.tools.viewer.xdf_viewer path/to/file.xdf
uv run python -m paradigm.tools.normalize_logs data/sub-P001
uv run python -m paradigm.tools.export.export_bids data/sub-P001/ses-S01/doors/20260324_120000 --bids-root bids_dataset
uv run python -m paradigm.tools.export.export_rdm data/sub-P001/ses-S01/rdm/20260324_120000/trial_summary.csv
uv run python -m paradigm.tools.analysis.export_task_metrics data/sub-P001/ses-S01/prl/20260324_120000
uv run python -m paradigm.tools.analysis.audit_run_logs data/sub-P001/ses-S01/prl/20260324_120000 --strict
```

其中：

- `paradigm.tools.normalize_logs` 负责 post-run 归一化与补齐。
- `paradigm.tools.export.export_bids` 负责 BIDS 行为/事件导出。
- `paradigm.tools.export.export_rdm` 负责 RDM 的 psychometric、chronometric 与 DDM-ready 表格。
- `paradigm.tools.analysis.export_task_metrics` 负责从单次 run 目录导出任务级行为摘要 JSON/CSV。
- `paradigm.tools.analysis.audit_run_logs` 负责审计单次 run 的事件完整性、时长、掉帧和 marker 字段语义；practice 模式会在运行结束后自动落一份同名报告。

## Export and Tests

BIDS-ready behavior/events 导出：

```bash
uv run python -m paradigm.tools.export.export_bids data/sub-P001/ses-S01/doors/20260324_120000 --bids-root bids_dataset
```

RDM 导出：

```bash
uv run python -m paradigm.tools.export.export_rdm data/sub-P001/ses-S01/rdm/20260324_120000/trial_summary.csv
```

测试：

```bash
uv run python -m unittest discover -s paradigm/tests -t . -v
```
