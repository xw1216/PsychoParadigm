# Project Guidelines

## Build and Test
- 在项目根目录优先使用 conda 环境 `psycho` 运行命令。
- 运行任务：`conda run -n psycho python main.py doors --participant P001 --session S01 --windowed`，`prl` 与 `rdm` 同理。
- 运行测试：`conda run -n psycho python -m unittest discover -s paradigm/tests -t . -v`。
- 导出 BIDS：`conda run -n psycho python -m paradigm.scripts.export_bids <run_dir> --bids-root <bids_root>`。
- LSL 与 XDF 工具分别使用 `python -m tools.lsl_monitor`、`python -m tools.xdf_viewer`。

## Architecture
- CLI 入口在 [main.py](../main.py) 与 [paradigm/app.py](../paradigm/app.py)；配置定义集中在 [paradigm/config.py](../paradigm/config.py)。
- 新任务或任务改动应遵循 [paradigm/runtime/base_experiment.py](../paradigm/runtime/base_experiment.py) 的生命周期、marker、日志与 run summary 契约。
- 事件码、marker 后端、日志字段与 schema 分别以 [paradigm/runtime/event_codes.py](../paradigm/runtime/event_codes.py)、[paradigm/runtime/markers.py](../paradigm/runtime/markers.py)、[paradigm/runtime/logging_utils.py](../paradigm/runtime/logging_utils.py)、[paradigm/runtime/schemas.py](../paradigm/runtime/schemas.py) 为准。

## Conventions
- 保持语义事件主键格式 `<task>.<phase>.<event>`；硬件 marker code 是 0 到 255 的单字节值，不要把它当作独立语义编号。
- `event_log.csv` 是逐事件真源，`trial_summary.csv` 是逐 trial 汇总；如果新增分析派生字段，优先放入 `task_specific_data` JSON，而不是继续扩展共享顶层列。
- 修改配置时不要直接改写 `DEFAULT_CONFIG`；沿用 [paradigm/app.py](../paradigm/app.py) 中的 CLI override 流程，或使用 deep copy 保持默认配置不可变。
- 缺失 flip 的事件时间统一使用 `-1.0`，不要写空值或改成其他哨兵值。

## Working Rules
- 这个仓库用 `unittest`，不是 `pytest`；新增或修改行为时，优先补充对应的单元测试或集成测试。
- 如果改动事件字典、日志字段、导出格式或用户可见 CLI/数据契约，同时更新 [README.md](../README.md) 与相关测试，尤其是 `test_readme_consistency` 一类文档一致性检查。
- 开发与调试阶段默认把 LPT、ioHub、LSL 当作可选硬件路径处理；除非任务明确要求硬件联调，否则不要假设本机一定有这些设备或依赖可用。

## References
- 项目运行方式、输出目录与工具说明见 [README.md](../README.md)。
- 配置覆盖与默认值不可变的测试示例见 [paradigm/tests/unit/test_app_config.py](../paradigm/tests/unit/test_app_config.py)。
- marker 行为与边界条件示例见 [paradigm/tests/unit/test_markers.py](../paradigm/tests/unit/test_markers.py)。
- PsychoPy 生命周期与 flip/marker/logger 契约示例见 [paradigm/tests/integration/test_psychopy_contracts.py](../paradigm/tests/integration/test_psychopy_contracts.py)。