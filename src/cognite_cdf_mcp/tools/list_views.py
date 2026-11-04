"""Tool: list CDF views."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.params import DEFAULT_LIMIT, optional_str

logger = logging.getLogger(__name__)


def _serialize_view_summary(view: Any) -> dict[str, Any]:
    return {
        "space": view.space,
        "externalId": view.external_id,
        "version": view.version,
        "name": view.name,
        "description": view.description,
        "usedFor": view.used_for,
        "isGlobal": view.is_global,
        "writable": getattr(view, "writable", None),
    }


def list_views(
    client: CogniteClient,
    *,
    space: str | None = None,
    all_versions: bool = False,
    include_global: bool = False,
    limit: int = DEFAULT_LIMIT,
) -> str:
    """List views in the CDF project (lean metadata, no property dump)."""
    space = optional_str(space)
    try:
        views = client.data_modeling.views.list(
            space=space,
            all_versions=all_versions,
            include_global=include_global,
            include_inherited_properties=False,
            limit=limit,
        )
        payload = {
            "count": len(views),
            "items": [_serialize_view_summary(v) for v in views],
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
