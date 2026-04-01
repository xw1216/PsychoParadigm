# PsychoParadigm

一个面向 EEG / LSL / LPT marker / eye tracking 扩展的 PsychoPy 实验项目骨架。当前内置 `doors`、`prl`、`rdm` 三个任务，并保留统一的事件码、日志、导出与硬件 marker 管线。

更详细的结构说明见 [docs/architecture.md](docs/architecture.md)，LPT 后端说明见 [docs/hardware-lpt.md](docs/hardware-lpt.md)。

## Quick Start

默认推荐：

```bash
uv run python main.py doors --participant P001 --session S01 --windowed
uv run python main.py prl --participant P001 --session S01 --windowed
uv run python main.py rdm --participant P001 --session S01 --windowed
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

其中：

- `event_log.csv` 是逐事件真源。
- `trial_summary.csv` 是逐 trial 汇总。
- `run_metadata.json` 会记录 `run_summary_schema`、marker backend 状态和配置快照。

## Package Layout

当前主结构：

- `paradigm.contracts`: 事件码、schema、validation
- `paradigm.data`: 日志写出、BIDS 导出、RDM 导出、normalize
- `paradigm.hardware.markers`: marker manager 与 LPT backend
- `paradigm.runtime`: 实验生命周期与 runtime session
- `paradigm.tasks`: 任务包
- `paradigm.tasks.<task>.<task>_logic`: 可在 headless 环境导入的纯逻辑层
- `paradigm.tools`: 包内工具实现

## Tools

工具入口：

```bash
uv run python -m paradigm.tools.viewer.lsl_monitor
uv run python -m paradigm.tools.viewer.xdf_viewer path/to/file.xdf
uv run python -m paradigm.tools.normalize_logs data/sub-P001
uv run python -m paradigm.tools.export.export_bids data/sub-P001/ses-S01/doors/20260324_120000 --bids-root bids_dataset
uv run python -m paradigm.tools.export.export_rdm data/sub-P001/ses-S01/rdm/20260324_120000/trial_summary.csv
```

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
