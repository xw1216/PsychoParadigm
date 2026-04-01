# PsychoParadigm

一个使用纯 psychopy-lib 编写的实验项目骨架，面向 EEG、Eye Tracker 预留、LSL、LPT marker、高精度计时、BIDS-ready 行为/事件导出和详细日志记录，并提供 fNIRS marker namespace 与日志层支持。

## 目录结构

```text
PsychoParadigm/
├── main.py
├── test.py
├── tools/
│   ├── adapters/
│   │   ├── base.py
│   │   ├── lsl_adapter.py
│   │   └── xdf_adapter.py
│   ├── matplotlib_views.py
│   ├── lsl_monitor.py
│   ├── stream_types.py
│   └── xdf_viewer.py
├── paradigm/
│   ├── __init__.py
│   ├── app.py
│   ├── config.py
│   ├── scripts/
│   │   ├── export_bids.py
│   │   └── export_rdm.py
│   ├── runtime/
│   │   ├── __init__.py
│   │   ├── base_experiment.py
│   │   ├── logging_utils.py
│   │   ├── markers.py
│   │   ├── schemas.py
│   │   └── utils.py
│   └── tasks/
│       ├── __init__.py
│       ├── doors.py
│       ├── prl.py
│       └── rdm.py
│   └── tests/
│       ├── integration/
│       │   └── test_psychopy_contracts.py
│       └── unit/
│           ├── test_logging_utils.py
│           ├── test_markers.py
│           └── test_task_generation.py
```

## 已实现内容

- 纯 Python + psychopy-lib，不依赖 Builder
- 统一任务入口
- Doors / PRL / RDM 三个任务
- LSL marker stream
- 基于 PsychoPy 并口接口的 LPT marker 输出
- 语义事件主键加单字节硬件 marker code 设计，例如 doors.fixation.onset -> 11
- 视觉 onset 与 marker 的 flip 同步发送
- 事件日志、trial summary、metadata、frame interval 落盘
- ioHub 眼动初始化与 AOI transition event logging
- fNIRS marker namespace 与日志字段支持
- PRL 的 RL 建模输出字段
- RDM 的 psychometric / DDM 导出
- BIDS-ready behavior/events 转换脚本
- escape 安全退出

三个任务的当前定位：

- Doors: 干净、稳定的反馈链路验证任务，主要用于 feedback-locked EEG smoke test，以及 RewP / FRN / feedback-theta 验证
- PRL: 当前最适合做主 pilot 的概率反转学习任务，聚焦学习更新、reversal 后恢复，以及 expected / unexpected outcome
- RDM: 当前默认实现是带 trial-wise correctness feedback 的版本，主要仍面向 coherence-accuracy/RT、CPP / response-locked 动力学与 sensorimotor beta 分析

## 已稳定实现 / 已预留但未完全封板

已稳定实现：

- semantic event_key 加单字节硬件 marker code 的运行时事件注册与日志链路
- LSL marker、LPT marker、flip 同步发送、event_log.csv / trial_summary.csv / run_metadata.json
- fNIRS namespace 命名与日志字段支持，包括 fnirs_marker_codes、fnirs_sent 和 metadata 中的 fnirs_mode
- Doors / PRL / RDM 当前主流程与对应导出
- PRL 的 expectedness / trial_phase / timeout policy 输出
- RDM 的 correctness feedback 版本、exclude_trial / exclude_reason 语义与导出

已预留但未完全封板：

- RDM 的 no-feedback 模式目前是低成本配置钩子，不是独立封板范式
- confidence rating 目前仅保留 confidence_rating_enabled 钩子
- 眼动 trial-level summary 接口字段已经预留，但多数仍需结合 AOI transition event_log 做离线汇总
- fNIRS 具体硬件协议适配尚未实现；当前稳定的是 namespace 与日志层，不是厂商设备直连封装

## 运行方式

在项目根目录运行：

默认使用 `uv run`。如果你已经维护了本地 conda 环境 `psycho`，下面所有命令都可以等价替换为 `conda run -n psycho python ...`。

```bash
uv run python main.py doors --participant P001 --session S01 --windowed
uv run python main.py prl --participant P001 --session S01 --windowed
uv run python main.py rdm --participant P001 --session S01 --windowed
```

如果需要启用 LPT：

```bash
uv run python main.py doors --participant P001 --session S01 --enable-lpt
```

如果要禁用 LSL：

```bash
uv run python main.py doors --participant P001 --session S01 --disable-lsl
```

如果未指定 participant 或 session，脚本启动后会在命令行提示输入。命令行参数只作为对配置默认值的覆盖。

你还可以单独覆盖 ioHub：

```bash
uv run python main.py doors --enable-iohub
```

每个任务都支持 practice 模式，用现有任务类直接跑短版流程：

```bash
uv run python main.py doors --participant P001 --session S01 --practice --windowed
uv run python main.py prl --participant P001 --session S01 --practice --windowed
uv run python main.py rdm --participant P001 --session S01 --practice --windowed
```

practice 模式默认配置：

- Doors: 1 block x 6 trials
- PRL: 2 blocks x 6 trials
- RDM: 1 block，每个方向 x 每个 practice coherence 1 次，默认 6 trials

任务正式开始前会先显示一屏等待页，用于确认 LabRecorder 已订阅 LSL marker 流。该屏支持的按键：

- F9: 在检测到订阅后继续
- F10: 强制继续，不等待订阅
- F6: 刷新当前状态
- escape: 安全退出

## 数据输出

每次运行输出到：

```text
data/sub-<participant>/ses-<session>/<task>/<timestamp>/
```

输出文件包括：

- run_metadata.json
- event_log.csv
- trial_summary.csv
- frame_intervals.csv
- rdm_psychometric_summary.csv
- rdm_ddm_ready.csv

其中 psychopy.log 默认不再输出；只有在配置里显式打开 `logging.save_psychopy_log` 时才会落盘。

trial_summary.csv 当前收敛为稳定公共列为主，任务特异或分析派生字段尽量进入 task_specific_data。核心列包括：

- participant
- session
- task
- block
- trial_index
- condition
- stimulus_parameters
- response
- rt
- correct
- feedback
- timeout
- fixation_onset
- stim_onset
- response_time_abs
- feedback_onset
- iti_onset
- trial_end
- lsl_marker_codes
- lpt_marker_codes
- event_keys
- fnirs_marker_codes
- task_specific_data

说明：

- event_log.csv 是逐事件真源
- trial_summary.csv 是逐 trial 汇总
- event_keys 只是 trial 级摘要字段，不替代 event_log.csv 的真源语义
- event_code 指单字节硬件 marker code，用于 LSL/LPT 运行时传输与日志，不应被理解为独立的逻辑语义码
- fnirs_marker_codes 反映的是 fNIRS namespace 日志层；它说明命名与记录链路存在，不等于某个具体 fNIRS 设备协议已经完成适配
- `stimulus_parameters`、`task_specific_data`、`extra_metadata` 统一写成单行 UTF-8 JSON，中文直接输出，不再转成 `\uXXXX`
- `event_log.csv` 中没有 flip 的事件统一写入非法值 `-1.0`，不再留空

其中：

- Doors 的 post_choice_delay_onset、反馈事件键等信息写入 task_specific_data；其中 post_choice_delay_onset 被视为 Doors 特有的关键 phase timestamp，当前有意保留在 task_specific_data 而不平铺为共享列
- Doors 的 `condition` 继续表达预设 gain/loss 条件，但 timeout / miss trial 的 `feedback` 与 `feedback_event` 会单独写成 `timeout` / `doors.feedback.timeout`，不与真实 gain/loss outcome 混淆
- PRL 的 reversal 边界、RL 建模字段写入 task_specific_data；其中 chosen_good、trial_phase、outcome_expectedness、prediction_error 虽然属于主分析字段，但当前仍通过 task_specific_data 承载，以避免继续加宽共享主表
- RDM 的 response_locked_rt、cpp_slope_proxy、exclude_trial 等写入 task_specific_data

run_metadata.json 还会额外写入 schema 说明，便于后处理程序明确读取：

- run_mode: 当前为 main 或 practice
- event_codebook: 运行时事件字典，组织方式为 task -> event_key -> entry
- event_codebook_schema: event_codebook 的字段说明，其中 event_code 明确表示单字节硬件 marker code，而不是通用逻辑语义编号
- task_specific_data_schema: 当前任务 task_specific_data 的边界说明、主分析字段提示与字段说明
- run_summary_schema: 当前任务 run_summary 的字段契约，供自动 QC 脚本直接消费
- run_summary: 任务结束时写入的轻量 quick QC 摘要

极简结构示例：

```json
{
	"event_codebook": {
		"doors": {
			"doors.choice.onset": {
				"event_code": 12,
				"description": "Door choice screen onset."
			}
		}
	}
}
```

```json
{
	"run_summary": {
		"n_trials": 80,
		"timeout_rate": 0.025,
		"gain_trials": 40,
		"loss_trials": 40,
		"feedback_event_complete": true
	}
}
```

## LPT 后端说明

LPT 逻辑位于 [paradigm/runtime/markers.py](paradigm/runtime/markers.py)。

设计要点：

- 统一由 MarkerManager 调度，不在任务代码中散落硬件调用
- 统一使用 PsychoPy 提供的 parallel 接口
- 优先兼容 `ParallelPort`，必要时回退到 `Parallel`
- 测试通过注入假的 parallel module 完成，不再单独维护虚拟并口实现
- 支持脉冲式置位后清零
- marker code 限制在 0 到 255，避免无效并口写值
- runtime 日志字段统一使用 event_key 和 event_code
- 事件语义由字符串主键表达，硬件只传输简单数值码，例如 doors.choice.onset -> 12

如果 PsychoPy 当前环境没有可用的 parallel API，LPT 后端会在 metadata 和状态里明确标记为不可用。

## BIDS 转换

项目提供单次运行目录到 BIDS behavior/events 文件的转换脚本：

```bash
uv run python -m paradigm.scripts.export_bids data/sub-P001/ses-S01/doors/20260324_120000 --bids-root bids_dataset
```

该脚本会生成：

- dataset_description.json
- participants.tsv
- sub-<participant>/ses-<session>/beh/*_events.tsv
- sub-<participant>/ses-<session>/beh/*_events.json
- sub-<participant>/ses-<session>/beh/*_beh.tsv
- sub-<participant>/ses-<session>/beh/*_beh.json

当前转换重点覆盖行为与事件层，生成的是 BIDS-ready artifacts，而不是完整 BIDS 原始数据集；后续仍需再与 EEG、fNIRS 或眼动原始数据做联合组织。

这也意味着当前目录中的：

- run_metadata.json
- event_log.csv
- trial_summary.csv
- frame_intervals.csv
- psychopy.log

都应被理解为 runtime artifacts / 中间层，而不是完整 BIDS raw dataset。

其中 fNIRS 相关输出目前应理解为 namespace/logging artifacts：事件命名、fnirs_marker_codes 和 fnirs_sent 已稳定实现，但具体硬件协议适配与厂商设备对接仍未封板。

## 便捷工具脚本

### 轻量 LSL 实时监视器

新的轻量监视器位于顶层 `tools/` 目录，当前优先支持离散 marker 流，并为后续 EEG / fNIRS / eye tracker 轨道扩展保留统一数据模型与 adapter 接口：

```bash
uv run python -m tools.lsl_monitor
```

常用参数：

- `--stream-name`: 指定要订阅的流名
- `--stream-index`: 按发现列表中的序号选择
- `--resolve-timeout`: 等待流出现的秒数
- `--window-seconds`: 实时窗口长度
- `--max-events`: 内存中保留的最近事件数量
- `--refresh-ms`: matplotlib 刷新间隔
- `--list-only`: 只列出 stream，不打开图形

示例：

```bash
uv run python -m tools.lsl_monitor --stream-name PsychoParadigmMarkers
```

当前版本特性：

- 自动发现并列出 LSL streams
- 当前优先支持 marker stream
- 实时显示最近一段时间窗口内的 marker
- 显示 stream name、source id、最新 marker、最新时间戳
- 支持 Start / Stop 按钮和空格键切换监视状态
- 保留共享时间轴和 adapter 架构，后续可以在不推翻结构的情况下扩到 EEG / fNIRS / eye tracker

### 轻量 XDF viewer

新的 XDF viewer 同样位于顶层 `tools/`，当前先把 marker 流支持做扎实：

```bash
uv run python -m tools.xdf_viewer path/to/recording.xdf
```

常用参数：

- `--stream-name`: 只选择指定名字的 marker 流
- `--stream-index`: 按列表中的序号选择 marker 流
- `--list-only`: 只列出 streams
- `--export-path`: 按 `e` 导出当前可见 marker 表时使用的路径

这个脚本会：

- 打印 XDF 内流的摘要信息
- 让用户选择一个 marker stream
- 用 matplotlib 显示 marker 时间轴和 marker 列表
- 直接显示 marker 数值，避免一开始做复杂 GUI
- 支持缩放、平移、点击 marker 跳转到对应时间
- 支持按 `e` 导出当前可见 marker 表

依赖说明：

- 运行 `tools.xdf_viewer` 需要当前环境已安装 `pyxdf` 和 `matplotlib`
- 如果缺少依赖，脚本会直接提示缺失的包名

## 三个任务的当前主流程

Doors:

- doors.experiment.start
- doors.block.start
- doors.fixation.onset
- doors.choice.onset
- doors.response.left 或 doors.response.right 或 doors.response.timeout
- doors.post_choice_delay.onset
- doors.feedback.gain 或 doors.feedback.loss 或 doors.feedback.timeout
- doors.iti.onset
- doors.block.end
- doors.experiment.end

Doors 保持为简单反馈任务，不按复杂学习任务解释。当前重点是让 feedback onset、marker 与日志链路稳定、可验证、可做 smoke test。

补充语义约束：

- timeout / miss 与真实负反馈严格区分
- timeout trial 会单独写成 `doors.response.timeout` 和 `doors.feedback.timeout`
- `condition` 可继续表达原始 gain/loss 条件，而 `feedback` 表达实际显示的反馈语义

PRL:

- prl.experiment.start
- prl.block.start
- prl.reversal.boundary 在 contingency 切换边界触发，不表示被试主观检测到 reversal 的时刻
- prl.fixation.onset
- prl.choice.onset
- prl.response.left 或 prl.response.right 或 prl.response.timeout
- prl.feedback.reward 或 prl.feedback.no_reward
- prl.iti.onset
- prl.block.end
- prl.experiment.end

PRL 中的 prl.reversal.boundary 表示 contingency 或 block 切换边界事件，不表示被试主观检测到 reversal 的时间点。

当前 PRL 还会输出：

- outcome expectedness 分层字段，支持 expected_reward / unexpected_reward / expected_no_reward / unexpected_no_reward
- trial_phase 字段，支持 initial_stable / early_post_reversal / relearning / late_stable / stable_pre_reversal
- timeout policy 字段，明确 timeout trial 不做 RL update，不计入 choice-dynamics 分析，并记录 timeout feedback 与 exclude_reason
- chosen_good、trial_phase、outcome_expectedness、prediction_error 是 PRL 的主分析字段，但当前仍通过 task_specific_data 承载
- 眼动 trial-level summary 接口字段已经预留，但当前多数仍需结合 AOI transition event_log 离线汇总
- 默认参数比早期版本更紧凑：更多 reversal、较短 block、稍弱确定性，尽量避免被试过早学穿后机械执行

RDM:

- 当前实现是带 trial-wise correctness feedback 的版本
- rdm.experiment.start
- rdm.block.start
- rdm.fixation.onset
- rdm.motion.onset
- rdm.response.left 或 rdm.response.right 或 rdm.response.timeout
- rdm.feedback.correct 或 rdm.feedback.incorrect
- rdm.iti.onset
- rdm.block.end
- rdm.experiment.end

RDM 当前默认 feedback_mode 为 correctness，并已为后续 no-feedback 纯 accumulation 版本预留配置钩子。若 feedback_mode 设为 none，则跳过反馈事件与反馈显示。

另外当前还预留了 practice staircase / 阈值估计相关配置钩子，但尚未封板为完整自适应流程。

RDM 当前的 fixation break / exclusion 语义为：

- online fixation break detection 默认未启用
- fixation break 当前主要服务于标记与排除语义，不构成完整在线控制闭环
- timeout 可按配置作为 exclude_trial 条件
- task_specific_data 中会写入 exclude_trial、exclude_reason、fixation_break_detected、fixation_break_online_detection、invalid_response；当前 exclude_reason 可能为 fixation_break、invalid_response 或 timeout
- confidence rating 暂未实现，但已预留 confidence_rating_enabled 配置钩子

## Runtime Event 范围

当前主 runtime event codebook 仅保留稳定、真实会在实验运行中发出的事件，以及明确的 system 事件：

- 任务起止、block 起止、break 起止
- fixation / stimulus / response / feedback / iti
- AOI transition
- system.safe_exit.requested
- system.frame.dropped_warning
- system.startup.failure

像 response-locked export helper、fixation break 这类更偏分析派生或尚未稳定触发的语义，不再放在主 runtime event codebook 中，改由 trial_summary 的 task_specific_data 承载。

## 日志字段命名

event_log.csv 的主字段为：

- event_index
- iso_time
- abs_time
- task_time
- task
- block
- trial
- event_key
- event_code
- flip_time
- lsl_sent
- lpt_sent
- fnirs_sent
- extra_metadata

这些字段在 runtime 日志、trial summary 摘要字段、README 和 BIDS-ready 导出中保持同一套命名：event_key / event_code；trial 级摘要中的有序事件列表统一命名为 event_keys。

其中 event_code 始终表示单字节硬件 marker code。真正的实验语义应由 event_key 解读，而不是把 event_code 当作通用语义编码体系。

fnirs_sent 表示 fNIRS namespace payload 是否经当前 LSL 输出链路发送成功；它不表示某个具体 fNIRS 设备协议写入已经实现。

## Runtime Event 与 task_specific_data 对照

Doors:

| runtime event | 含义 | task_specific_data 字段 |
| --- | --- | --- |
| doors.fixation.onset | 选择前注视点开始 | 无 |
| doors.choice.onset | door 选择界面出现 | 无 |
| doors.response.left / doors.response.right / doors.response.timeout | 响应或超时 | response_event |
| doors.post_choice_delay.onset | 选择后延迟开始 | post_choice_delay_onset |
| doors.feedback.gain / doors.feedback.loss | trial-wise feedback | feedback_event, feedback_type |
| doors.iti.onset | trial ITI 开始 | 无 |

PRL:

| runtime event | 含义 | task_specific_data 字段 |
| --- | --- | --- |
| prl.reversal.boundary | contingency 切换边界，不是被试主观察觉 reversal 的时刻 | is_reversal_boundary, trial_in_block, good_side |
| prl.fixation.onset | 选择前注视点开始 | 无 |
| prl.choice.onset | 选择界面出现 | choice_probability_left, q_left, q_right |
| prl.response.left / prl.response.right / prl.response.timeout | 响应或超时 | response_event, switch_from_previous |
| prl.feedback.reward / prl.feedback.no_reward | outcome feedback | feedback_event, reward, chosen_good, prediction_error |
| prl.iti.onset | trial ITI 开始 | 无 |

RDM:

| runtime event | 含义 | task_specific_data 字段 |
| --- | --- | --- |
| rdm.fixation.onset | motion 前注视点开始 | 无 |
| rdm.motion.onset | random dot motion 出现 | direction, coherence |
| rdm.response.left / rdm.response.right / rdm.response.timeout | 响应或超时 | response_event, response_locked_rt |
| rdm.feedback.correct / rdm.feedback.incorrect | correctness feedback，当前实现按 trial 给反馈 | feedback_event, cpp_slope_proxy |
| rdm.iti.onset | trial ITI 开始 | fixation_break_detected, exclude_trial |

这里的 task_specific_data 主要用于容纳任务特异或分析辅助字段，避免继续加宽共享 trial_summary 主表。

需要特别注意的是：task_specific_data 并不等同于“次要字段”。对 PRL 而言，chosen_good、trial_phase、outcome_expectedness、prediction_error 属于主分析字段，只是当前为了保持共享列稳定而暂留在 task_specific_data。

## Quick QC

Quick QC 仅用于现场快速判断运行状态，不替代正式离线预处理与质量控制流程。

每个任务当前都会在 run_metadata.json 的 run_summary 中写入轻量 QC 摘要，便于现场快速判断数据是否正常。建议最小成功标准：

- Doors: 低漏答率、gain/loss 近似平衡、feedback events 完整
- PRL: 高概率选项选择率随 block 内进程上升，reversal 后能逐步恢复
- RDM: coherence 越高 accuracy 越高，RT 整体更短，timeout 率保持较低

run_metadata.json 还会同步写入 run_summary_schema，便于后续自动 QC 脚本不依赖任务实现细节，直接按 common_fields + task_fields 读取和校验对应摘要键。

硬件与时序层面，还应关注：

- event_log.csv 中 event_key / event_code 是否完整
- frame_intervals.csv 是否出现明显 dropped frame
- metadata 中 marker_status 与 eye_tracker_status 是否符合预期

## 测试

当前测试分为两层：

- 单元测试：LPT/marker、日志、trial 生成逻辑
- PsychoPy 契约测试：验证 flip 时 marker 回调与键盘时钟重置等时序约束

新增工具脚本相关的基础验证包括：

- CLI 交互提示在正常输入和 EOF 条件下的回退行为
- LSL consumer 状态查询
- marker logging 的 JSON 序列化稳定性

当前关键契约覆盖包括：

- PRL 的 expectedness、trial_phase 和 timeout policy 语义
- RDM 的 feedback_mode=none 预留钩子
- RDM 的 exclude_trial / exclude_reason / invalid_response 规则一致性
- event_code 的单字节范围与全局唯一性
- fNIRS namespace 状态字段与日志层边界

运行测试：

```bash
uv run python -m unittest discover -s paradigm/tests -t . -v
```
