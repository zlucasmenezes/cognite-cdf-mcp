"""Tool: aggregate CDF instances through a view."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.instances_common import InstanceType, dump_maybe, view_id
from cognite_cdf_mcp.tools.params import (
    DEFAULT_LIMIT,
    optional_str,
    parse_filter,
    parse_json_object,
)

logger = logging.getLogger(__name__)


def _normalize_aggregate_property(value: Any) -> Any:
    """CDF aggregate endpoints expect a property *string* for view/top-level fields.

    Accept common path forms and coerce them:
    - "name" / "externalId"
    - ["externalId"] -> "externalId"
    - ["node", "externalId"] -> "externalId"
    - ["space", "View/v1", "name"] -> "name"
    """
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value:
        if len(value) == 1 and isinstance(value[0], str):
            return value[0]
        if len(value) == 2 and value[0] in {"node", "edge"} and isinstance(value[1], str):
            return value[1]
        if len(value) >= 3 and isinstance(value[-1], str):
            return value[-1]
    return value


def _normalize_aggregates(aggregates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in aggregates:
        if not isinstance(item, dict) or len(item) != 1:
            raise TypeError("each aggregate must be an object with one metric key")
        metric, body = next(iter(item.items()))
        if not isinstance(body, dict):
            raise TypeError(f"aggregate {metric!r} body must be an object")
        body = dict(body)
        if "property" in body:
            body["property"] = _normalize_aggregate_property(body["property"])
        normalized.append({metric: body})
    return normalized


def aggregate_instances(
    client: CogniteClient,
    *,
    view_space: str,
    view_external_id: str,
    view_version: str,
    aggregates: list[dict[str, Any]] | dict[str, Any] | str,
    group_by: list[str] | str | None = None,
    instance_space: str | None = None,
    instance_type: InstanceType = "node",
    query: str | None = None,
    filter: dict[str, Any] | str | None = None,  # noqa: A002
    limit: int = DEFAULT_LIMIT,
) -> str:
    """Aggregate instances (count/sum/avg/min/max) through a view.

    ``aggregates`` examples (property is a string relative to the view)::
      {"count": {"property": "externalId"}}
      [{"avg": {"property": "temperature"}}]

    ``query`` is forwarded without an ``operator``. The aggregate SDK method
    has no operator parameter, so text matching follows the API default.
    SDK instance search defaults to AND; this tool does not apply that default.

    Requires ``dataModelInstancesAcl:READ``.
    """
    try:
        source = view_id(
            view_space=view_space,
            view_external_id=view_external_id,
            view_version=view_version,
        )
        parsed_aggregates = parse_json_object(aggregates)
        if parsed_aggregates is None:
            raise ValueError("aggregates is required")
        if isinstance(parsed_aggregates, dict):
            parsed_aggregates = [parsed_aggregates]
        if not isinstance(parsed_aggregates, list) or not parsed_aggregates:
            raise TypeError("aggregates must be a non-empty object or array of objects")
        parsed_aggregates = _normalize_aggregates(parsed_aggregates)

        parsed_group_by: list[str] | None = None
        if group_by is not None:
            if isinstance(group_by, list):
                parsed_group_by = [str(_normalize_aggregate_property(p)) for p in group_by]
            else:
                loaded = parse_json_object(group_by)
                if isinstance(loaded, list):
                    parsed_group_by = [str(_normalize_aggregate_property(x)) for x in loaded]
                else:
                    parsed_group_by = [p.strip() for p in group_by.split(",") if p.strip()]

        result = client.data_modeling.instances.aggregate(
            view=source,
            aggregates=parsed_aggregates,
            group_by=parsed_group_by,
            instance_type=instance_type,
            query=optional_str(query),
            space=optional_str(instance_space),
            filter=parse_filter(filter),
            limit=limit,
        )
        return json.dumps(
            {
                "limit": limit,
                "result": dump_maybe(result),
            },
            indent=2,
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return json.dumps({"error": "InvalidArgument", "message": str(exc)})
    except CogniteAPIError as exc:
        logger.exception("CDF API error aggregating instances")
        return json.dumps(
            {
                "error": "CogniteAPIError",
                "code": getattr(exc, "code", None),
                "message": str(exc),
            }
        )
    except CogniteException as exc:
        logger.exception("Cognite error aggregating instances")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error aggregating instances")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
