"""Tool: delete CDF instances (nodes/edges) with dry-run."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import EdgeId, NodeId, ViewId
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.instances_common import (
    InstanceType,
    as_instance_list,
    serialize_instance,
)
from cognite_cdf_mcp.tools.params import (
    DEFAULT_DRY_RUN,
    MAX_INSTANCE_WRITE_BATCH,
    chunk,
    parse_object_list,
)

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


def _delete_cognite_error(
    exc: CogniteException,
    *,
    completed_batches: int,
    items: list[dict[str, str]],
) -> str:
    if isinstance(exc, CogniteAPIError):
        logger.exception("CDF API error deleting instances")
        body: dict[str, Any] = {
            "error": "CogniteAPIError",
            "code": getattr(exc, "code", None),
            "message": str(exc),
        }
    else:
        logger.exception("Cognite error deleting instances")
        body = {"error": type(exc).__name__, "message": str(exc)}
    if completed_batches:
        body["completedBatches"] = completed_batches
        body["items"] = items
    return json.dumps(body)


def _optional_view(item: dict[str, Any]) -> ViewId | None:
    space = item.get("viewSpace") or item.get("view_space")
    external_id = item.get("viewExternalId") or item.get("view_external_id")
    version = item.get("viewVersion") or item.get("view_version")
    present = [space, external_id, version]
    if all(value is None or not str(value).strip() for value in present):
        return None
    if any(value is None or not str(value).strip() for value in present):
        raise ValueError("viewSpace, viewExternalId, and viewVersion must all be set together")
    return ViewId(
        space=str(space).strip(),
        external_id=str(external_id).strip(),
        version=str(version).strip(),
    )


def _group_ids_by_view(
    ids: list[tuple[str, str]],
    views: list[ViewId | None],
) -> list[tuple[ViewId | None, list[tuple[str, str]]]]:
    order: list[tuple[str, str, str] | None] = []
    groups: dict[tuple[str, str, str] | None, list[tuple[str, str]]] = {}
    for (space, external_id), view in zip(ids, views, strict=True):
        key = None if view is None else (view.space, view.external_id, view.version)
        if key not in groups:
            order.append(key)
            groups[key] = []
        groups[key].append((space, external_id))
    grouped: list[tuple[ViewId | None, list[tuple[str, str]]]] = []
    for key in order:
        view = None if key is None else ViewId(space=key[0], external_id=key[1], version=key[2])
        grouped.append((view, groups[key]))
    return grouped


def _id_dict(item: Any) -> dict[str, Any]:
    return {
        "space": getattr(item, "space", None),
        "externalId": getattr(item, "external_id", None),
    }


def delete_instances(
    client: CogniteClient,
    *,
    items: list[dict[str, Any]] | str,
    instance_type: InstanceType = "node",
    dry_run: bool = DEFAULT_DRY_RUN,
) -> str:
    """Delete one or more instances by space/externalId.

    ``items`` example: [{"space": "sp_x", "externalId": "MCH-1"}]
    Defaults to ``DEFAULT_DRY_RUN`` (retrieve/report only). Pass ``dry_run=false``
    to delete. Requires ``dataModelInstancesAcl:WRITE`` for an actual delete.

    Deletes are chunked to at most ``MAX_INSTANCE_WRITE_BATCH`` (1000) ids per
    CDF call. If a later chunk fails, the error includes ``completedBatches``
    and the ids already deleted.

    Deleting a node also deletes edges that start or end on it. Too many
    connected edges can make the real delete fail; dry run does not check that.
    If an item includes ``viewSpace``, ``viewExternalId``, and ``viewVersion``,
    dry-run retrieve uses that view. Items without a view are retrieved without one.
    """
    try:
        raw_items = parse_object_list(items)
        ids = _parse_ids(raw_items)
        if not ids:
            raise ValueError("items must contain at least one instance id")
        views = [_optional_view(item) for item in raw_items]

        id_batches = chunk(ids, MAX_INSTANCE_WRITE_BATCH)

        if dry_run:
            found: list[Any] = []
            retrieve_calls = 0
            for view, group in _group_ids_by_view(ids, views):
                sources = [view] if view is not None else None
                for batch in chunk(group, MAX_INSTANCE_WRITE_BATCH):
                    retrieve_calls += 1
                    if instance_type == "edge":
                        existing = client.data_modeling.instances.retrieve_edges(
                            edges=[EdgeId(space=s, external_id=e) for s, e in batch],
                            sources=sources,
                        )
                    else:
                        existing = client.data_modeling.instances.retrieve_nodes(
                            nodes=[NodeId(space=s, external_id=e) for s, e in batch],
                            sources=sources,
                        )
                    found.extend(as_instance_list(existing))
            if instance_type == "node":
                message = (
                    "Dry run only — instances were not deleted. "
                    "Missing ids are omitted from items. "
                    "Deleting a node also deletes edges that start or end on it. "
                    "Too many connected edges can make the real delete fail."
                )
            else:
                message = (
                    "Dry run only — instances were not deleted. Missing ids are omitted from items."
                )
            return json.dumps(
                {
                    "dryRun": True,
                    "wouldDelete": len(found) > 0,
                    "requested": len(ids),
                    "found": len(found),
                    "batches": retrieve_calls,
                    "maxBatchSize": MAX_INSTANCE_WRITE_BATCH,
                    "items": [serialize_instance(i) for i in found],
                    "message": message,
                },
                indent=2,
            )

        deleted_nodes: list[Any] = []
        deleted_edges: list[Any] = []
        deleted_ids: list[dict[str, str]] = []
        completed_batches = 0
        for batch in id_batches:
            try:
                if instance_type == "edge":
                    deleted = client.data_modeling.instances.delete(
                        edges=[EdgeId(space=s, external_id=e) for s, e in batch]
                    )
                else:
                    deleted = client.data_modeling.instances.delete(
                        nodes=[NodeId(space=s, external_id=e) for s, e in batch]
                    )
            except CogniteException as exc:
                return _delete_cognite_error(
                    exc,
                    completed_batches=completed_batches,
                    items=deleted_ids,
                )
            completed_batches += 1
            deleted_ids.extend(
                {"space": space, "externalId": external_id} for space, external_id in batch
            )
            deleted_nodes.extend(list(getattr(deleted, "nodes", []) or []))
            deleted_edges.extend(list(getattr(deleted, "edges", []) or []))

        node_items = [_id_dict(item) for item in deleted_nodes]
        edge_items = [_id_dict(item) for item in deleted_edges]
        return json.dumps(
            {
                "dryRun": False,
                "deleted": bool(node_items or edge_items),
                "count": len(node_items) + len(edge_items),
                "batches": len(id_batches),
                "maxBatchSize": MAX_INSTANCE_WRITE_BATCH,
                "nodes": node_items,
                "edges": edge_items,
                "items": [*node_items, *edge_items],
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
