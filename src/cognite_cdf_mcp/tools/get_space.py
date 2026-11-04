"""Tool: retrieve a specific CDF space."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.errors import not_found_space

logger = logging.getLogger(__name__)


def _serialize_space(space: Any) -> dict[str, Any]:
    return {
        "space": space.space,
        "name": space.name,
        "description": space.description,
        "isGlobal": space.is_global,
        "createdTime": getattr(space, "created_time", None),
        "lastUpdatedTime": getattr(space, "last_updated_time", None),
    }


def get_space(
    client: CogniteClient,
    *,
    space: str,
) -> str:
    """Retrieve one space by id."""
    try:
        result = client.data_modeling.spaces.retrieve(spaces=space)
        if result is None:
            return json.dumps(not_found_space(client, space), indent=2)
        # SDK returns Space for a single id, SpaceList for multiple.
        item = result[0] if hasattr(result, "__iter__") and not hasattr(result, "space") else result
        return json.dumps({"item": _serialize_space(item)}, indent=2)
    except CogniteAPIError as exc:
        logger.exception("CDF API error retrieving space")
        return json.dumps(
            {
                "error": "CogniteAPIError",
                "code": getattr(exc, "code", None),
                "message": str(exc),
            }
        )
    except CogniteException as exc:
        logger.exception("Cognite error retrieving space")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error retrieving space")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
