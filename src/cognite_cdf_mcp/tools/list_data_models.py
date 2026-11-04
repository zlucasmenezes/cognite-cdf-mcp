"""Tool: list CDF data models."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.params import DEFAULT_LIMIT, optional_str
from cognite_cdf_mcp.tools.schema_page import RESOURCE_DATA_MODELS, fetch_schema_page

logger = logging.getLogger(__name__)


def _view_ref(view: dict[str, Any]) -> dict[str, Any]:
    return {
        "space": view.get("space"),
        "externalId": view.get("externalId"),
        "version": view.get("version"),
    }


def _serialize_data_model(item: dict[str, Any]) -> dict[str, Any]:
    views = item.get("views") or []
    return {
        "space": item.get("space"),
        "externalId": item.get("externalId"),
        "version": item.get("version"),
        "name": item.get("name"),
        "description": item.get("description"),
        "isGlobal": item.get("isGlobal"),
        "views": [_view_ref(v) for v in views if isinstance(v, dict)],
    }


def list_data_models(
    client: CogniteClient,
    *,
    space: str | None = None,
    all_versions: bool = False,
    include_global: bool = False,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> str:
    """List data models in the CDF project (cursor-paginated).

    Returns lean model metadata and view references (without inlined views).
    """
    try:
        items, next_cursor = fetch_schema_page(
            client,
            resource_path=RESOURCE_DATA_MODELS,
            params={
                "space": optional_str(space),
                "allVersions": all_versions,
                "includeGlobal": include_global,
                "inlineViews": False,
            },
            limit=limit,
            cursor=cursor,
        )
        payload = {
            "count": len(items),
            "limit": limit,
            "nextCursor": next_cursor,
            "items": [_serialize_data_model(m) for m in items],
        }
        return json.dumps(payload, indent=2)
    except CogniteAPIError as exc:
        logger.exception("CDF API error listing data models")
        return json.dumps(
            {
                "error": "CogniteAPIError",
                "code": exc.code,
                "message": str(exc),
            }
        )
    except CogniteException as exc:
        logger.exception("Cognite error listing data models")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error listing data models")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
