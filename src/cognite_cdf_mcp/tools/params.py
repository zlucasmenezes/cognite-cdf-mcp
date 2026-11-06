"""Normalize MCP tool inputs from hosts/inspectors."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any, TypeVar

DEFAULT_LIMIT = 100

# CDF Data Modeling limits:
# https://docs.cognite.com/api-reference/concepts/20230101/instances (apply/delete ≤1000)
# https://docs.cognite.com/cdf/dm/dm_reference/dm_limits_and_restrictions
MAX_INSTANCE_WRITE_BATCH = 1000
MAX_IN_FILTER_VALUES = 1000

# Experimental safety: write tools preview by default. Flip to False when ready
# for opt-out dry-run (and update README / tool descriptions accordingly).
DEFAULT_DRY_RUN = True

T = TypeVar("T")


def chunk(items: Sequence[T], size: int) -> list[list[T]]:
    """Split ``items`` into consecutive chunks of at most ``size``."""
    if size <= 0:
        raise ValueError("chunk size must be positive")
    return [list(items[i : i + size]) for i in range(0, len(items), size)]


def optional_str(value: str | None) -> str | None:
    """Treat blank strings as missing (MCP hosts often send ``\"\"``)."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def parse_json_object(
    value: dict[str, Any] | list[Any] | str | None,
) -> dict[str, Any] | list[Any] | None:
    """Accept a JSON object/array or a JSON string encoding one."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value or None
    stripped = value.strip()
    if not stripped:
        return None
    parsed = json.loads(stripped)
    if not isinstance(parsed, (dict, list)):
        raise TypeError("value must be a JSON object or array")
    return parsed or None


def _validate_in_filters(node: Any, *, path: str = "filter") -> None:
    """Raise if any ``in`` filter lists more than ``MAX_IN_FILTER_VALUES`` values."""
    if isinstance(node, list):
        for i, child in enumerate(node):
            _validate_in_filters(child, path=f"{path}[{i}]")
        return
    if not isinstance(node, dict):
        return
    if "in" in node:
        spec = node["in"]
        values = spec.get("values") if isinstance(spec, dict) else None
        if isinstance(values, list) and len(values) > MAX_IN_FILTER_VALUES:
            raise ValueError(
                f"{path}.in.values has {len(values)} entries; CDF allows at most "
                f"{MAX_IN_FILTER_VALUES}. Split into batches of {MAX_IN_FILTER_VALUES} "
                "and merge results (see get_filter_docs)."
            )
    for key, child in node.items():
        if key in {"and", "or", "not"} or isinstance(child, (dict, list)):
            _validate_in_filters(child, path=f"{path}.{key}" if key != "not" else f"{path}.not")


def parse_filter(value: dict[str, Any] | str | None) -> dict[str, Any] | None:
    """Accept a CDF filter object or a JSON string encoding one."""
    parsed = parse_json_object(value)
    if parsed is None:
        return None
    if not isinstance(parsed, dict):
        raise TypeError("filter must be a JSON object")
    _validate_in_filters(parsed)
    return parsed


def parse_object_list(value: list[Any] | str | None) -> list[Any]:
    """Accept a list of objects or a JSON string encoding one."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    stripped = value.strip()
    if not stripped:
        return []
    parsed = json.loads(stripped)
    if not isinstance(parsed, list):
        raise TypeError("expected a JSON array")
    return parsed
