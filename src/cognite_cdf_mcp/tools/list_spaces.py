"""Tool: list CDF spaces."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.params import DEFAULT_LIMIT
from cognite_cdf_mcp.tools.schema_page import RESOURCE_SPACES, fetch_schema_page

logger = logging.getLogger(__name__)


def _serialize_space_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "space": item.get("space"),
        "name": item.get("name"),
        "description": item.get("description"),
        "isGlobal": item.get("isGlobal"),
    }


def list_spaces(
    client: CogniteClient,
    *,
    include_global: bool = False,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> str:
    """List spaces in the CDF project (cursor-paginated)."""
    try:
        items, next_cursor = fetch_schema_page(
            client,
            resource_path=RESOURCE_SPACES,
            params={"includeGlobal": include_global},
            limit=limit,
            cursor=cursor,
        )
        payload = {
            "count": len(items),
            "limit": limit,
            "nextCursor": next_cursor,
            "items": [_serialize_space_item(s) for s in items],
        }
        return json.dumps(payload, indent=2)
    except CogniteAPIError as exc:
        logger.exception("CDF API error listing spaces")
        return json.dumps(
            {
                "error": "CogniteAPIError",
                "code": exc.code,
                "message": str(exc),
            }
        )
    except CogniteException as exc:
        logger.exception("Cognite error listing spaces")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error listing spaces")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
