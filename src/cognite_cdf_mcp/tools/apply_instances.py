"""Tool: create/update CDF instances with dry-run."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import (
    DirectRelationReference,
    EdgeApply,
    EdgeId,
    NodeApply,
    NodeId,
    NodeOrEdgeData,
    ViewId,
)
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.access import (
    INSTANCES_ACL,
    check_spaces,
    denial_detail,
    is_denied,
)
from cognite_cdf_mcp.tools.instances_common import serialize_instance
from cognite_cdf_mcp.tools.params import (
    DEFAULT_DRY_RUN,
    MAX_INSTANCE_WRITE_BATCH,
    chunk,
    parse_object_list,
)

logger = logging.getLogger(__name__)


def _view_from_item(item: dict[str, Any]) -> ViewId:
    space = item.get("viewSpace") or item.get("view_space")
    external_id = item.get("viewExternalId") or item.get("view_external_id")
    version = item.get("viewVersion") or item.get("view_version")
    if not space or not external_id or not version:
        raise ValueError(
            "each node/edge with properties requires viewSpace, viewExternalId, and viewVersion"
        )
    return ViewId(space=str(space), external_id=str(external_id), version=str(version))


def _parse_node(item: dict[str, Any]) -> NodeApply:
    space = item.get("space")
    external_id = item.get("externalId") or item.get("external_id")
    if not space or not external_id:
        raise ValueError("each node requires space and externalId")
    properties = item.get("properties")
    sources = None
    if properties is not None:
        if not isinstance(properties, dict):
            raise TypeError("node properties must be an object")
        sources = [NodeOrEdgeData(source=_view_from_item(item), properties=properties)]
    node_type = item.get("type")
    type_ref = None
    if isinstance(node_type, dict):
        type_ref = DirectRelationReference(
            space=str(node_type["space"]),
            external_id=str(node_type.get("externalId") or node_type.get("external_id")),
        )
    elif isinstance(node_type, (list, tuple)) and len(node_type) == 2:
        type_ref = (str(node_type[0]), str(node_type[1]))
    return NodeApply(
        space=str(space),
        external_id=str(external_id),
        existing_version=item.get("existingVersion", item.get("existing_version")),
        sources=sources,
        type=type_ref,
    )


def _parse_edge(item: dict[str, Any]) -> EdgeApply:
    space = item.get("space")
    external_id = item.get("externalId") or item.get("external_id")
    start_node = item.get("startNode") or item.get("start_node")
    end_node = item.get("endNode") or item.get("end_node")
    edge_type = item.get("type")
    if not space or not external_id:
        raise ValueError("each edge requires space and externalId")
    if not isinstance(start_node, dict) or not isinstance(end_node, dict):
        raise ValueError("each edge requires startNode and endNode objects")
    if not isinstance(edge_type, dict):
        raise ValueError("each edge requires type {space, externalId}")

    properties = item.get("properties")
    sources = None
    if properties is not None:
        if not isinstance(properties, dict):
            raise TypeError("edge properties must be an object")
        sources = [NodeOrEdgeData(source=_view_from_item(item), properties=properties)]

    return EdgeApply(
        space=str(space),
        external_id=str(external_id),
        type=DirectRelationReference(
            space=str(edge_type["space"]),
            external_id=str(edge_type.get("externalId") or edge_type.get("external_id")),
        ),
        start_node=DirectRelationReference(
            space=str(start_node["space"]),
            external_id=str(start_node.get("externalId") or start_node.get("external_id")),
        ),
        end_node=DirectRelationReference(
            space=str(end_node["space"]),
            external_id=str(end_node.get("externalId") or end_node.get("external_id")),
        ),
        existing_version=item.get("existingVersion", item.get("existing_version")),
        sources=sources,
    )


def _access_on_forbidden(
    client: CogniteClient,
    exc: CogniteException,
    spaces: list[str],
) -> dict[str, Any] | None:
    if not isinstance(exc, CogniteAPIError) or getattr(exc, "code", None) != 403:
        return None
    return check_spaces(client, acl=INSTANCES_ACL, action="WRITE", spaces=spaces)


def _instance_ref(item: Any) -> dict[str, str]:
    return {"space": str(item.space), "externalId": str(item.external_id)}


def _combined_write_batches(
    node_applies: list[NodeApply],
    edge_applies: list[EdgeApply],
) -> list[tuple[list[NodeApply], list[EdgeApply]]]:
    """All nodes, then all edges, in slices of at most ``MAX_INSTANCE_WRITE_BATCH``."""
    sequence: list[tuple[str, Any]] = [("node", node) for node in node_applies]
    sequence.extend(("edge", edge) for edge in edge_applies)
    batches: list[tuple[list[NodeApply], list[EdgeApply]]] = []
    for group in chunk(sequence, MAX_INSTANCE_WRITE_BATCH):
        nodes = [item for kind, item in group if kind == "node"]
        edges = [item for kind, item in group if kind == "edge"]
        batches.append((nodes, edges))
    return batches


def _apply_cognite_error(
    exc: CogniteException,
    *,
    completed_batches: int,
    nodes: list[dict[str, str]],
    edges: list[dict[str, str]],
    access: dict[str, Any] | None = None,
) -> str:
    if isinstance(exc, CogniteAPIError):
        logger.exception("CDF API error applying instances")
        body: dict[str, Any] = {
            "error": "CogniteAPIError",
            "code": getattr(exc, "code", None),
            "message": str(exc),
        }
        if access is not None:
            body["access"] = access
    else:
        logger.exception("Cognite error applying instances")
        body = {"error": type(exc).__name__, "message": str(exc)}
    if completed_batches:
        body["completedBatches"] = completed_batches
        body["nodes"] = nodes
        body["edges"] = edges
    return json.dumps(body)


def apply_instances(
    client: CogniteClient,
    *,
    nodes: list[dict[str, Any]] | str | None = None,
    edges: list[dict[str, Any]] | str | None = None,
    replace: bool = False,
    auto_create_direct_relations: bool = True,
    dry_run: bool = DEFAULT_DRY_RUN,
) -> str:
    """Create or update instances (upsert).

    Node item example::
      {
        "space": "sp_x",
        "externalId": "MCH-1",
        "viewSpace": "cdf_cdm",
        "viewExternalId": "CogniteAsset",
        "viewVersion": "v1",
        "properties": {"name": "Pump A"},
        "existingVersion": 3
      }

    Defaults to ``DEFAULT_DRY_RUN`` (validates / retrieves existing; no write).
    Pass ``dry_run=false`` to apply. Requires ``dataModelInstancesAcl:WRITE``
    for an actual write.

    Writes send all nodes first, then all edges, in chunks of at most
    ``MAX_INSTANCE_WRITE_BATCH`` (1000) items combined per CDF apply call.
    If a later chunk fails, the error includes ``completedBatches`` and the
    ids already applied.
    """
    instance_spaces: list[str] = []
    try:
        node_items = parse_object_list(nodes)
        edge_items = parse_object_list(edges)
        if not node_items and not edge_items:
            raise ValueError("provide at least one node or edge")

        node_applies = [_parse_node(item) for item in node_items]
        edge_applies = [_parse_edge(item) for item in edge_items]
        write_batches = _combined_write_batches(node_applies, edge_applies)
        instance_spaces = [node.space for node in node_applies] + [
            edge.space for edge in edge_applies
        ]

        if dry_run:
            existing_nodes: list[Any] = []
            existing_edges: list[Any] = []
            for batch in chunk(node_applies, MAX_INSTANCE_WRITE_BATCH):
                retrieved = client.data_modeling.instances.retrieve_nodes(
                    nodes=[NodeId(n.space, n.external_id) for n in batch]
                )
                if retrieved is not None:
                    existing_nodes.extend(list(retrieved))
            for batch in chunk(edge_applies, MAX_INSTANCE_WRITE_BATCH):
                retrieved_e = client.data_modeling.instances.retrieve_edges(
                    edges=[EdgeId(e.space, e.external_id) for e in batch]
                )
                if retrieved_e is not None:
                    existing_edges.extend(list(retrieved_e))
            access = check_spaces(
                client,
                acl=INSTANCES_ACL,
                action="WRITE",
                spaces=instance_spaces,
            )
            denied = is_denied(access)
            message = "Dry run only — instances were not written."
            if denied:
                message = f"{message} {denial_detail(access)}"
            return json.dumps(
                {
                    "dryRun": True,
                    "wouldApply": not denied,
                    "replace": replace,
                    "batches": len(write_batches),
                    "maxBatchSize": MAX_INSTANCE_WRITE_BATCH,
                    "access": access,
                    "nodes": {
                        "requested": len(node_applies),
                        "alreadyExist": len(existing_nodes),
                        "payload": [n.dump(camel_case=True) for n in node_applies],
                        "existing": [serialize_instance(n) for n in existing_nodes],
                    },
                    "edges": {
                        "requested": len(edge_applies),
                        "alreadyExist": len(existing_edges),
                        "payload": [e.dump(camel_case=True) for e in edge_applies],
                        "existing": [serialize_instance(e) for e in existing_edges],
                    },
                    "message": message,
                },
                indent=2,
            )

        applied_nodes: list[Any] = []
        applied_edges: list[Any] = []
        applied_node_ids: list[dict[str, str]] = []
        applied_edge_ids: list[dict[str, str]] = []
        completed_batches = 0
        for nodes_batch, edges_batch in write_batches:
            try:
                result = client.data_modeling.instances.apply(
                    nodes=nodes_batch or None,
                    edges=edges_batch or None,
                    replace=replace,
                    auto_create_direct_relations=auto_create_direct_relations,
                )
            except CogniteException as exc:
                return _apply_cognite_error(
                    exc,
                    completed_batches=completed_batches,
                    nodes=applied_node_ids,
                    edges=applied_edge_ids,
                    access=_access_on_forbidden(client, exc, instance_spaces),
                )
            completed_batches += 1
            applied_node_ids.extend(_instance_ref(node) for node in nodes_batch)
            applied_edge_ids.extend(_instance_ref(edge) for edge in edges_batch)
            applied_nodes.extend(list(getattr(result, "nodes", []) or []))
            applied_edges.extend(list(getattr(result, "edges", []) or []))

        return json.dumps(
            {
                "dryRun": False,
                "applied": True,
                "replace": replace,
                "batches": len(write_batches),
                "maxBatchSize": MAX_INSTANCE_WRITE_BATCH,
                "nodes": {
                    "count": len(applied_nodes),
                    "items": [serialize_instance(n) for n in applied_nodes],
                },
                "edges": {
                    "count": len(applied_edges),
                    "items": [serialize_instance(e) for e in applied_edges],
                },
            },
            indent=2,
        )
    except (TypeError, ValueError, json.JSONDecodeError, KeyError) as exc:
        return json.dumps({"error": "InvalidArgument", "message": str(exc)})
    except CogniteAPIError as exc:
        logger.exception("CDF API error applying instances")
        body = {
            "error": "CogniteAPIError",
            "code": getattr(exc, "code", None),
            "message": str(exc),
        }
        access = _access_on_forbidden(client, exc, instance_spaces)
        if access is not None:
            body["access"] = access
        return json.dumps(body)
    except CogniteException as exc:
        logger.exception("Cognite error applying instances")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error applying instances")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
