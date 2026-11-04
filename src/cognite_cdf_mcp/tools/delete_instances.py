"""Tool: delete CDF instances (nodes/edges) with dry-run."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import EdgeId, NodeId
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.instances_common import InstanceType, serialize_instance
from cognite_cdf_mcp.tools.params import parse_object_list

logger = logging.getLogger(__name__)


def _parse_ids(items: list[Any]) -> list[tuple[str, str]]:
    parsed: list[tuple[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            raise TypeError("each item must be an object with space and externalId")
        space = item.get("space")
        external_id = item.get("externalId") or item.get("external_id")
        if not space or not external_id:
            raise ValueError("each item requires space and externalId")
        parsed.append((str(space), str(external_id)))
    return parsed


def delete_instances(
    client: CogniteClient,
    *,
    items: list[dict[str, Any]] | str,
    instance_type: InstanceType = "node",
    dry_run: bool = False,
) -> str:
    """Delete one or more instances by space/externalId.

    ``items`` example: [{"space": "sp_x", "externalId": "MCH-1"}]
    dry_run=true retrieves and reports only (no delete).
    Requires ``dataModelInstancesAcl:WRITE`` for an actual delete.
    """
    try:
        ids = _parse_ids(parse_object_list(items))
        if not ids:
            raise ValueError("items must contain at least one instance id")

        if instance_type == "edge":
            edge_ids = [EdgeId(space=s, external_id=e) for s, e in ids]
            if dry_run:
                existing = client.data_modeling.instances.retrieve_edges(edges=edge_ids)
                found = list(existing) if existing is not None else []
                return json.dumps(
                    {
                        "dryRun": True,
                        "wouldDelete": len(found) > 0,
                        "requested": len(ids),
                        "found": len(found),
                        "items": [serialize_instance(i) for i in found],
                        "message": (
                            "Dry run only — instances were not deleted. "
                            "Missing ids are omitted from items."
                        ),
                    },
                    indent=2,
                )
            deleted = client.data_modeling.instances.delete(edges=edge_ids)
        else:
            node_ids = [NodeId(space=s, external_id=e) for s, e in ids]
            if dry_run:
                existing = client.data_modeling.instances.retrieve_nodes(nodes=node_ids)
                found = list(existing) if existing is not None else []
                return json.dumps(
                    {
                        "dryRun": True,
                        "wouldDelete": len(found) > 0,
                        "requested": len(ids),
                        "found": len(found),
                        "items": [serialize_instance(i) for i in found],
                        "message": (
                            "Dry run only — instances were not deleted. "
                            "Missing ids are omitted from items."
                        ),
                    },
                    indent=2,
                )
            deleted = client.data_modeling.instances.delete(nodes=node_ids)

        deleted_nodes = list(getattr(deleted, "nodes", []) or [])
        deleted_edges = list(getattr(deleted, "edges", []) or [])
        deleted_items = deleted_nodes or deleted_edges
        return json.dumps(
            {
                "dryRun": False,
                "deleted": len(deleted_items) > 0,
                "count": len(deleted_items),
                "items": [
                    {
                        "space": getattr(i, "space", None),
                        "externalId": getattr(i, "external_id", None),
                    }
                    for i in deleted_items
                ],
            },
            indent=2,
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return json.dumps({"error": "InvalidArgument", "message": str(exc)})
    except CogniteAPIError as exc:
        logger.exception("CDF API error deleting instances")
        return json.dumps(
            {
                "error": "CogniteAPIError",
                "code": getattr(exc, "code", None),
                "message": str(exc),
            }
        )
    except CogniteException as exc:
        logger.exception("Cognite error deleting instances")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error deleting instances")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
