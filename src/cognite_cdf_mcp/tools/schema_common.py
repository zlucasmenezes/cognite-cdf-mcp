"""Shared helpers for schema write tools (views / containers / data models)."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.params import MAX_SCHEMA_PER_REQUEST, chunk

logger = logging.getLogger(__name__)


def as_list(result: Any) -> list[Any]:
    """Normalize a retrieve/apply result to a list (None, one item, or many)."""
    if result is None:
        return []
    if isinstance(result, list):
        return list(result)
    if hasattr(result, "space") and not hasattr(result, "__iter__"):
        return [result]
    return list(result)


def dump_schema(item: Any) -> dict[str, Any]:
    """Serialize a schema object with the SDK dump when available."""
    dump = getattr(item, "dump", None)
    if callable(dump):
        dumped = dump(camel_case=True)
        if isinstance(dumped, dict):
            return dumped
    return {
        "space": getattr(item, "space", None),
        "externalId": getattr(item, "external_id", None),
        "version": getattr(item, "version", None),
        "name": getattr(item, "name", None),
        "description": getattr(item, "description", None),
    }


def schema_batches(items: list[Any]) -> list[list[Any]]:
    """Split schema items into CDF-sized batches (≤100)."""
    return chunk(items, MAX_SCHEMA_PER_REQUEST)


def partial_cognite_error(
    exc: CogniteException,
    *,
    completed_batches: int,
    items: list[dict[str, Any]],
    action: str,
) -> str:
    """JSON error body when a later schema batch fails after earlier success."""
    if isinstance(exc, CogniteAPIError):
        logger.exception("CDF API error %s schema", action)
        body: dict[str, Any] = {
            "error": "CogniteAPIError",
            "code": getattr(exc, "code", None),
            "message": str(exc),
        }
    else:
        logger.exception("Cognite error %s schema", action)
        body = {"error": type(exc).__name__, "message": str(exc)}
    if completed_batches:
        body["completedBatches"] = completed_batches
        body["items"] = items
    return json.dumps(body)


def require_object_list(items: list[Any], *, label: str) -> list[dict[str, Any]]:
    """Validate that every list entry is a dict (MCP hosts may send mixed arrays)."""
    if not items:
        raise ValueError(f"provide at least one {label}")
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise TypeError(f"each {label} item must be an object")
        out.append(item)
    return out
