"""Tool: list CDF views."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.params import DEFAULT_LIMIT, optional_str
from cognite_cdf_mcp.tools.schema_page import RESOURCE_VIEWS, fetch_schema_page

logger = logging.getLogger(__name__)


def _serialize_view_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "space": item.get("space"),
        "externalId": item.get("externalId"),
        "version": item.get("version"),
        "name": item.get("name"),
        "description": item.get("description"),
        "usedFor": item.get("usedFor"),
        "isGlobal": item.get("isGlobal"),
        "writable": item.get("writable"),
    }


def list_views(
    client: CogniteClient,
    *,
    space: str | None = None,
    all_versions: bool = False,
    include_global: bool = False,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> str:
    """List views in the CDF project (lean metadata, cursor-paginated)."""
    space = optional_str(space)
    try:
        items, next_cursor = fetch_schema_page(
            client,
            resource_path=RESOURCE_VIEWS,
            params={
                "space": space,
                "allVersions": all_versions,
                "includeGlobal": include_global,
                "includeInheritedProperties": False,
            },
            limit=limit,
            cursor=cursor,
        )
        payload = {
            "count": len(items),
            "limit": limit,
            "nextCursor": next_cursor,
            "items": [_serialize_view_summary(v) for v in items],
        }
        return json.dumps(payload, indent=2)
    except CogniteAPIError as exc:
        logger.exception("CDF API error listing views")
        return json.dumps(
            {
                "error": "CogniteAPIError",
                "code": getattr(exc, "code", None),
                "message": str(exc),
            }
        )
    except CogniteException as exc:
        logger.exception("Cognite error listing views")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error listing views")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
