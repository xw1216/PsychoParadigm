from __future__ import annotations

import os
from pathlib import Path

from paradigm.config import MarkerConfig


def resolve_lsl_api_config_path(config: MarkerConfig) -> Path | None:
    if config.lsl_api_config:
        candidate = Path(config.lsl_api_config).expanduser()
        if candidate.exists():
            return candidate.resolve()
        return None

    project_default = Path(__file__).resolve().parents[3] / "lsl_api.cfg"
    if project_default.exists():
        return project_default.resolve()
    return None


def ensure_lsl_environment(config: MarkerConfig) -> str | None:
    if os.environ.get("LSLAPICFG"):
        return os.environ["LSLAPICFG"]
    resolved = resolve_lsl_api_config_path(config)
    if resolved is None:
        return None
    os.environ["LSLAPICFG"] = str(resolved)
    return str(resolved)