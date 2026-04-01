import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, ClassVar, Protocol, TypeGuard


class _DataclassInstance(Protocol):
    __dataclass_fields__: ClassVar[dict[str, Any]]


def _is_dataclass_instance(value: Any) -> TypeGuard[_DataclassInstance]:
    return is_dataclass(value) and not isinstance(value, type)


def dataclass_to_dict(value: Any) -> Any:
    if _is_dataclass_instance(value):
        return asdict(value)
    return value


def make_json_safe(value: Any) -> Any:
    if _is_dataclass_instance(value):
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
