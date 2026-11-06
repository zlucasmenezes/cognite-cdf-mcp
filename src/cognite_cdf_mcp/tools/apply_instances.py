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

    Writes are chunked to at most ``MAX_INSTANCE_WRITE_BATCH`` (1000) items per
    CDF apply call (Data Modeling limit).
    """
    try:
        node_items = parse_object_list(nodes)
        edge_items = parse_object_list(edges)
        if not node_items and not edge_items:
            raise ValueError("provide at least one node or edge")

        node_applies = [_parse_node(item) for item in node_items]
        edge_applies = [_parse_edge(item) for item in edge_items]
        node_batches = chunk(node_applies, MAX_INSTANCE_WRITE_BATCH) if node_applies else []
        edge_batches = chunk(edge_applies, MAX_INSTANCE_WRITE_BATCH) if edge_applies else []
        batch_count = max(len(node_batches), len(edge_batches), 1)

        if dry_run:
            existing_nodes: list[Any] = []
            existing_edges: list[Any] = []
            for batch in node_batches:
                retrieved = client.data_modeling.instances.retrieve_nodes(
                    nodes=[NodeId(n.space, n.external_id) for n in batch]
                )
                if retrieved is not None:
                    existing_nodes.extend(list(retrieved))
            for batch in edge_batches:
                retrieved_e = client.data_modeling.instances.retrieve_edges(
                    edges=[EdgeId(e.space, e.external_id) for e in batch]
                )
                if retrieved_e is not None:
                    existing_edges.extend(list(retrieved_e))
            return json.dumps(
                {
                    "dryRun": True,
                    "wouldApply": True,
                    "replace": replace,
                    "batches": batch_count,
                    "maxBatchSize": MAX_INSTANCE_WRITE_BATCH,
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
                    "message": "Dry run only — instances were not written.",
                },
                indent=2,
            )

        applied_nodes: list[Any] = []
        applied_edges: list[Any] = []
        # Pair node/edge batches by index; missing side is None for that apply call.
        for i in range(batch_count):
            nodes_batch = node_batches[i] if i < len(node_batches) else None
            edges_batch = edge_batches[i] if i < len(edge_batches) else None
            result = client.data_modeling.instances.apply(
                nodes=nodes_batch or None,
                edges=edges_batch or None,
                replace=replace,
                auto_create_direct_relations=auto_create_direct_relations,
            )
            applied_nodes.extend(list(getattr(result, "nodes", []) or []))
            applied_edges.extend(list(getattr(result, "edges", []) or []))

        return json.dumps(
            {
                "dryRun": False,
                "applied": True,
                "replace": replace,
                "batches": batch_count,
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
        return json.dumps(
            {
                "error": "CogniteAPIError",
                "code": getattr(exc, "code", None),
                "message": str(exc),
            }
        )
    except CogniteException as exc:
        logger.exception("Cognite error applying instances")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error applying instances")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
