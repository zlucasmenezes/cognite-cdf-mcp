"""Tool: query CDF instances by view and optional filter (with cursor)."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling.query import (
    EdgeResultSetExpression,
    NodeResultSetExpression,
    Query,
    Select,
    SourceSelector,
)
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.instances_common import (
    InstanceType,
    build_instance_filter,
    serialize_instance,
    view_id,
)
from cognite_cdf_mcp.tools.params import DEFAULT_LIMIT, optional_str, parse_filter

logger = logging.getLogger(__name__)

_RESULT_SET = "items"


def query_instances(
    client: CogniteClient,
    *,
    view_space: str,
    view_external_id: str,
    view_version: str,
    instance_space: str | None = None,
    instance_type: InstanceType = "node",
    filter: dict[str, Any] | str | None = None,  # noqa: A002
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
    include_typing: bool = False,
) -> str:
    """Query instances through a view, with optional space, filter, and cursor.

    Passing a view applies a ``hasData`` filter automatically.
    Requires ``dataModelInstancesAcl:READ``.
    """
    try:
        source = view_id(
            view_space=view_space,
            view_external_id=view_external_id,
            view_version=view_version,
        )
        parsed_filter = parse_filter(filter)
        combined = build_instance_filter(
            source=source,
            instance_type=instance_type,
            instance_space=instance_space,
            extra_filter=parsed_filter,
        )
        result_expr: NodeResultSetExpression | EdgeResultSetExpression
        if instance_type == "edge":
            result_expr = EdgeResultSetExpression(filter=combined, limit=limit)
        else:
            result_expr = NodeResultSetExpression(filter=combined, limit=limit)

        cursors: dict[str, str | None] = {}
        cursor_value = optional_str(cursor)
        if cursor_value is not None:
            cursors[_RESULT_SET] = cursor_value

        query = Query(
            with_={_RESULT_SET: result_expr},
            select={
                _RESULT_SET: Select(
                    sources=[SourceSelector(source, properties=["*"])],
                )
            },
            cursors=cursors,
        )
        result = client.data_modeling.instances.query(
            query,
            include_typing=include_typing,
        )
        items = list(result.get(_RESULT_SET, []))
        next_cursor = None
        if getattr(result, "cursors", None):
            next_cursor = result.cursors.get(_RESULT_SET)

        return json.dumps(
            {
                "count": len(items),
                "limit": limit,
                "nextCursor": next_cursor,
                "items": [serialize_instance(item) for item in items],
            },
            indent=2,
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return json.dumps({"error": "InvalidArgument", "message": str(exc)})
    except CogniteAPIError as exc:
        logger.exception("CDF API error querying instances")
        return json.dumps(
            {
                "error": "CogniteAPIError",
                "code": getattr(exc, "code", None),
                "message": str(exc),
            }
        )
    except CogniteException as exc:
        logger.exception("Cognite error querying instances")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error querying instances")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
