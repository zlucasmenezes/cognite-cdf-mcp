"""Tool: list CDF spaces."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.exceptions import CogniteAPIError, CogniteException

logger = logging.getLogger(__name__)


def _serialize_space(space: Any) -> dict[str, Any]:
    return {
        "space": space.space,
        "name": space.name,
        "description": space.description,
        "isGlobal": space.is_global,
    }


def list_spaces(
    client: CogniteClient,
    *,
    include_global: bool = False,
    limit: int | None = None,
) -> str:
    """List spaces in the CDF project."""
    try:
        spaces = client.data_modeling.spaces.list(
            include_global=include_global,
            limit=limit,
        )
        payload = {
            "count": len(spaces),
            "items": [_serialize_space(s) for s in spaces],
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
