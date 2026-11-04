"""Tool: list CDF containers."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.params import DEFAULT_LIMIT, optional_str
from cognite_cdf_mcp.tools.schema_page import RESOURCE_CONTAINERS, fetch_schema_page

logger = logging.getLogger(__name__)


def _serialize_container_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "space": item.get("space"),
        "externalId": item.get("externalId"),
        "name": item.get("name"),
        "description": item.get("description"),
        "usedFor": item.get("usedFor"),
        "isGlobal": item.get("isGlobal"),
    }


def list_containers(
    client: CogniteClient,
    *,
    space: str | None = None,
    include_global: bool = False,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> str:
    """List containers in the CDF project (lean metadata, cursor-paginated)."""
    try:
        items, next_cursor = fetch_schema_page(
            client,
            resource_path=RESOURCE_CONTAINERS,
            params={
                "space": optional_str(space),
                "includeGlobal": include_global,
            },
            limit=limit,
            cursor=cursor,
        )
        return json.dumps(
            {
                "count": len(items),
                "limit": limit,
                "nextCursor": next_cursor,
                "items": [_serialize_container_summary(c) for c in items],
            },
            indent=2,
        )
    except CogniteAPIError as exc:
        logger.exception("CDF API error listing containers")
        return json.dumps(
            {
                "error": "CogniteAPIError",
                "code": getattr(exc, "code", None),
                "message": str(exc),
            }
        )
    except CogniteException as exc:
        logger.exception("Cognite error listing containers")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error listing containers")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
