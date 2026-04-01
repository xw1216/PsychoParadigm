import argparse
import copy

from paradigm.config import DEFAULT_CONFIG
from paradigm.tasks import DoorsTask, PRLTask, RDMTask


TASK_REGISTRY = {
    "doors": DoorsTask,
    "prl": PRLTask,
    "rdm": RDMTask,
}


def apply_practice_overrides(config, task_name: str):
    config.practice.enabled = True
    config.common.break_every_n_trials = 9999
    if task_name == "doors":
        config.doors.blocks = config.doors.practice_blocks
        config.doors.trials_per_block = config.doors.practice_trials_per_block
    elif task_name == "prl":
        config.prl.blocks = config.prl.practice_blocks
        config.prl.trials_per_block = config.prl.practice_trials_per_block
    elif task_name == "rdm":
        config.rdm.blocks = config.rdm.practice_blocks
        config.rdm.trials_per_condition = config.rdm.practice_trials_per_condition
        config.rdm.coherence_levels = list(config.rdm.practice_coherence_levels)
    return config


def apply_cli_overrides(config, args: argparse.Namespace, task_name: str | None = None):
    updated = copy.deepcopy(config)
    if args.enable_lsl:
        updated.markers.enable_lsl = True
    if args.disable_lsl:
        updated.markers.enable_lsl = False
    if args.enable_lpt:
        updated.markers.enable_lpt = True
    if args.disable_lpt:
        updated.markers.enable_lpt = False
    if args.enable_iohub:
        updated.eye_tracker.enable_iohub = True
    if args.disable_iohub:
        updated.eye_tracker.enable_iohub = False
    if args.windowed:
        updated.screen.fullscr = False
    if args.practice and task_name is not None:
        updated = apply_practice_overrides(updated, task_name)
    return updated


def prompt_if_missing(value: str | None, prompt_text: str, fallback: str) -> str:
    if value:
        return value
    try:
        typed = input(f"{prompt_text} [{fallback}]: ").strip()
    except EOFError:
        return fallback
    return typed or fallback


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PsychoPy 实验任务启动器")
    parser.add_argument("task", nargs="?", choices=sorted(TASK_REGISTRY.keys()), help="要运行的任务")
    parser.add_argument("--participant", dest="participant", default=None, help="被试编号")
    parser.add_argument("--practice", action="store_true", help="以简短练习配置运行任务")
    parser.add_argument("--session", dest="session", default=None, help="session 编号")
    parser.add_argument("--windowed", action="store_true", help="以窗口模式运行，便于调试")
    
    parser.add_argument("--enable-lsl", action="store_true", help="为本次运行启用 LSL marker 输出")
    parser.add_argument("--disable-lsl", action="store_true", help="为本次运行禁用 LSL marker 输出")
    parser.add_argument("--enable-lpt", action="store_true", help="为本次运行启用 LPT marker 输出")
    parser.add_argument("--disable-lpt", action="store_true", help="为本次运行禁用 LPT marker 输出")
    parser.add_argument("--enable-iohub", action="store_true", help="启用 ioHub 眼动接口")
    parser.add_argument("--disable-iohub", action="store_true", help="禁用 ioHub 眼动接口")
    return parser.parse_args()

def main() -> None:
    args = parse_args()

    task_name = args.task or prompt_if_missing(None, "任务 (doors/prl/rdm)", "doors")
    participant = prompt_if_missing(args.participant, "被试编号", "P001")
    session = prompt_if_missing(args.session, "Session 编号", "S01")

    config = apply_cli_overrides(DEFAULT_CONFIG, args, task_name=task_name)

    task_cls = TASK_REGISTRY[task_name]
    task = task_cls(participant=participant, session=session, config=config)
    task.run()


if __name__ == "__main__":
    main()
