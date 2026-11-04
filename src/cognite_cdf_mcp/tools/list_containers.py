"""Tool: list CDF containers."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.params import DEFAULT_LIMIT, optional_str

logger = logging.getLogger(__name__)


def _serialize_container_summary(container: Any) -> dict[str, Any]:
    return {
        "space": container.space,
        "externalId": container.external_id,
        "name": container.name,
        "description": container.description,
        "usedFor": container.used_for,
        "isGlobal": container.is_global,
    }


def list_containers(
    client: CogniteClient,
    *,
    space: str | None = None,
    include_global: bool = False,
    limit: int = DEFAULT_LIMIT,
) -> str:
    """List containers in the CDF project (lean metadata)."""
    try:
        containers = client.data_modeling.containers.list(
            space=optional_str(space),
            include_global=include_global,
            limit=limit,
        )
        return json.dumps(
            {
                "count": len(containers),
                "limit": limit,
                "items": [_serialize_container_summary(c) for c in containers],
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
