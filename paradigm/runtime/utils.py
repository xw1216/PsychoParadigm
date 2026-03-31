import json
import random
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence, TypeVar


T = TypeVar("T")


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def timestamp_for_path() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def iso_timestamp() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


def sample_jitter(time_range_s: Sequence[float], rng: random.Random) -> float:
    start, end = float(time_range_s[0]), float(time_range_s[1])
    return rng.uniform(start, end)


def dataclass_to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    return value


def make_json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return make_json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(key): make_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [make_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "item") and callable(value.item):
        try:
            return make_json_safe(value.item())
        except (TypeError, ValueError):
            pass
    if hasattr(value, "tolist") and callable(value.tolist):
        try:
            return make_json_safe(value.tolist())
        except (TypeError, ValueError):
            pass
    return value


def to_json_string(value: Any) -> str:
    return json.dumps(make_json_safe(value), ensure_ascii=False, separators=(", ", ": "))


def balanced_binary_sequence(total_count: int, rng: random.Random) -> list[int]:
    sequence = [1] * (total_count // 2) + [0] * (total_count - total_count // 2)
    rng.shuffle(sequence)
    return sequence


def chunk_sequence(items: Sequence[T], chunk_size: int) -> list[list[T]]:
    return [list(items[index : index + chunk_size]) for index in range(0, len(items), chunk_size)]


def flatten(items: Iterable[Iterable[Any]]) -> list[Any]:
    return [item for sub_items in items for item in sub_items]
