"""Normalize MCP tool inputs from hosts/inspectors."""

from __future__ import annotations

import json
from typing import Any

DEFAULT_LIMIT = 100

# Experimental safety: write tools preview by default. Flip to False when ready
# for opt-out dry-run (and update README / tool descriptions accordingly).
DEFAULT_DRY_RUN = True


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


def parse_filter(value: dict[str, Any] | str | None) -> dict[str, Any] | None:
    """Accept a CDF filter object or a JSON string encoding one."""
    parsed = parse_json_object(value)
    if parsed is None:
        return None
    if not isinstance(parsed, dict):
        raise TypeError("filter must be a JSON object")
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
