"""Single-page schema list helpers with cursor (REST supports it; public SDK list does not)."""

from __future__ import annotations

from typing import Any

from cognite.client import CogniteClient

from cognite_cdf_mcp.tools.params import optional_str

RESOURCE_SPACES = "/models/spaces"
RESOURCE_VIEWS = "/models/views"
RESOURCE_DATA_MODELS = "/models/datamodels"
RESOURCE_CONTAINERS = "/models/containers"


def fetch_schema_page(
    client: CogniteClient,
    *,
    resource_path: str,
    params: dict[str, Any],
    limit: int,
    cursor: str | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """GET one page from a schema list endpoint; returns (items, nextCursor)."""
    query = {key: value for key, value in params.items() if value is not None}
    query["limit"] = limit
    cursor_value = optional_str(cursor)
    if cursor_value is not None:
        query["cursor"] = cursor_value

    url = f"/api/v1/projects/{client.config.project}{resource_path}"
    body = client.get(url, params=query).json()
    items = body.get("items") or []
    if not isinstance(items, list):
        raise TypeError("schema list response items must be an array")
    next_cursor = body.get("nextCursor")
    return items, next_cursor if isinstance(next_cursor, str) and next_cursor else None
