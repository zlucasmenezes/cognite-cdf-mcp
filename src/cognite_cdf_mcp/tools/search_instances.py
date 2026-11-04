"""Tool: search CDF instances by text query."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.instances_common import (
    InstanceType,
    serialize_instance,
    view_id,
)
from cognite_cdf_mcp.tools.params import DEFAULT_LIMIT, optional_str, parse_filter

logger = logging.getLogger(__name__)


def search_instances(
    client: CogniteClient,
    *,
    view_space: str,
    view_external_id: str,
    view_version: str,
    query: str,
    properties: list[str] | None = None,
    instance_space: str | None = None,
    instance_type: InstanceType = "node",
    filter: dict[str, Any] | str | None = None,  # noqa: A002
    limit: int = DEFAULT_LIMIT,
    include_typing: bool = False,
) -> str:
    """Full-text search instances through a view.

    Requires ``dataModelInstancesAcl:READ``.
    """
    try:
        source = view_id(
            view_space=view_space,
            view_external_id=view_external_id,
            view_version=view_version,
        )
        parsed_filter = parse_filter(filter)
        instances = client.data_modeling.instances.search(
            view=source,
            query=query,
            instance_type=instance_type,
            properties=properties,
            space=optional_str(instance_space),
            filter=parsed_filter,
            include_typing=include_typing,
            limit=limit,
        )
        return json.dumps(
            {
                "count": len(instances),
                "limit": limit,
                "query": query,
                "items": [serialize_instance(item) for item in instances],
            },
            indent=2,
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return json.dumps({"error": "InvalidArgument", "message": str(exc)})
    except CogniteAPIError as exc:
        logger.exception("CDF API error searching instances")
        return json.dumps(
            {
                "error": "CogniteAPIError",
                "code": getattr(exc, "code", None),
                "message": str(exc),
            }
        )
    except CogniteException as exc:
        logger.exception("Cognite error searching instances")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error searching instances")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
