"""Unit tests: apply/delete chunk at MAX_INSTANCE_WRITE_BATCH."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.apply_instances import apply_instances
from cognite_cdf_mcp.tools.delete_instances import delete_instances
from cognite_cdf_mcp.tools.params import MAX_INSTANCE_WRITE_BATCH


def _node_item(i: int) -> dict[str, Any]:
    return {
        "space": "sp_x",
        "externalId": f"n-{i}",
        "viewSpace": "vs",
        "viewExternalId": "V",
        "viewVersion": "v1",
        "properties": {"name": f"N{i}"},
    }


def _edge_item(i: int) -> dict[str, Any]:
    return {
        "space": "sp_x",
        "externalId": f"e-{i}",
        "startNode": {"space": "sp_x", "externalId": f"n-{i}"},
        "endNode": {"space": "sp_x", "externalId": f"n-{i}"},
        "type": {"space": "sp_x", "externalId": "rel"},
    }


def _ids(prefix: str, count: int) -> list[dict[str, str]]:
    return [{"space": "sp_x", "externalId": f"{prefix}-{i}"} for i in range(count)]


def test_apply_instances_chunks_writes() -> None:
    client = MagicMock()
    apply_result = SimpleNamespace(nodes=[], edges=[])
    client.data_modeling.instances.apply.return_value = apply_result

    n = MAX_INSTANCE_WRITE_BATCH + 50
    out = json.loads(
        apply_instances(
            client,
            nodes=[_node_item(i) for i in range(n)],
            dry_run=False,
        )
    )
    assert out["applied"] is True
    assert out["batches"] == 2
    assert out["maxBatchSize"] == MAX_INSTANCE_WRITE_BATCH
    assert client.data_modeling.instances.apply.call_count == 2
    first_nodes = client.data_modeling.instances.apply.call_args_list[0].kwargs["nodes"]
    second_nodes = client.data_modeling.instances.apply.call_args_list[1].kwargs["nodes"]
    assert len(first_nodes) == MAX_INSTANCE_WRITE_BATCH
    assert len(second_nodes) == 50
    assert client.data_modeling.instances.apply.call_args_list[0].kwargs["edges"] is None
    assert client.data_modeling.instances.apply.call_args_list[1].kwargs["edges"] is None


def test_apply_1000_nodes_and_1000_edges_are_two_calls() -> None:
    client = MagicMock()
    client.data_modeling.instances.apply.return_value = SimpleNamespace(nodes=[], edges=[])

    out = json.loads(
        apply_instances(
            client,
            nodes=[_node_item(i) for i in range(MAX_INSTANCE_WRITE_BATCH)],
            edges=[_edge_item(i) for i in range(MAX_INSTANCE_WRITE_BATCH)],
            dry_run=False,
        )
    )
    assert out["applied"] is True
    assert out["batches"] == 2
    calls = client.data_modeling.instances.apply.call_args_list
    assert len(calls) == 2
    assert len(calls[0].kwargs["nodes"]) == MAX_INSTANCE_WRITE_BATCH
    assert calls[0].kwargs["edges"] is None
    assert calls[1].kwargs["nodes"] is None
    assert [edge.external_id for edge in calls[1].kwargs["edges"]] == [
        f"e-{i}" for i in range(MAX_INSTANCE_WRITE_BATCH)
    ]


def test_apply_600_nodes_and_600_edges_keeps_nodes_before_edges() -> None:
    client = MagicMock()
    client.data_modeling.instances.apply.return_value = SimpleNamespace(nodes=[], edges=[])

    out = json.loads(
        apply_instances(
            client,
            nodes=[_node_item(i) for i in range(600)],
            edges=[_edge_item(i) for i in range(600)],
            dry_run=False,
        )
    )
    assert out["batches"] == 2
    calls = client.data_modeling.instances.apply.call_args_list
    assert len(calls) == 2
    assert [node.external_id for node in calls[0].kwargs["nodes"]] == [f"n-{i}" for i in range(600)]
    assert [edge.external_id for edge in calls[0].kwargs["edges"]] == [f"e-{i}" for i in range(400)]
    assert calls[1].kwargs["nodes"] is None
    assert [edge.external_id for edge in calls[1].kwargs["edges"]] == [
        f"e-{i}" for i in range(400, 600)
    ]
    assert len(calls[0].kwargs["nodes"]) + len(calls[0].kwargs["edges"]) == MAX_INSTANCE_WRITE_BATCH
    assert len(calls[1].kwargs["edges"]) == 200


def test_apply_dry_run_batches_follow_combined_write_chunks() -> None:
    client = MagicMock()
    client.data_modeling.instances.retrieve_nodes.return_value = []
    client.data_modeling.instances.retrieve_edges.return_value = []

    out = json.loads(
        apply_instances(
            client,
            nodes=[_node_item(i) for i in range(600)],
            edges=[_edge_item(i) for i in range(600)],
            dry_run=True,
        )
    )
    assert out["dryRun"] is True
    assert out["batches"] == 2
    assert client.data_modeling.instances.apply.call_count == 0
    assert client.data_modeling.instances.retrieve_nodes.call_count == 1
    assert client.data_modeling.instances.retrieve_edges.call_count == 1
    assert len(client.data_modeling.instances.retrieve_nodes.call_args.kwargs["nodes"]) == 600
    assert len(client.data_modeling.instances.retrieve_edges.call_args.kwargs["edges"]) == 600


def test_apply_second_batch_failure_reports_completed_ids() -> None:
    client = MagicMock()
    client.data_modeling.instances.apply.side_effect = [
        SimpleNamespace(nodes=[], edges=[]),
        CogniteAPIError("apply failed", 400),
    ]

    out = json.loads(
        apply_instances(
            client,
            nodes=[_node_item(i) for i in range(MAX_INSTANCE_WRITE_BATCH)],
            edges=[_edge_item(i) for i in range(MAX_INSTANCE_WRITE_BATCH)],
            dry_run=False,
        )
    )
    assert out["error"] == "CogniteAPIError"
    assert out["code"] == 400
    assert "apply failed" in out["message"]
    assert out["completedBatches"] == 1
    assert out["nodes"] == _ids("n", MAX_INSTANCE_WRITE_BATCH)
    assert out["edges"] == []
    assert client.data_modeling.instances.apply.call_count == 2


def test_apply_cognite_exception_on_later_batch_reports_completed_ids() -> None:
    client = MagicMock()
    client.data_modeling.instances.apply.side_effect = [
        SimpleNamespace(nodes=[], edges=[]),
        CogniteException("connection reset"),
    ]
    n = MAX_INSTANCE_WRITE_BATCH + 1
    out = json.loads(
        apply_instances(
            client,
            nodes=[_node_item(i) for i in range(n)],
            dry_run=False,
        )
    )
    assert out["error"] == "CogniteException"
    assert "connection reset" in out["message"]
    assert "code" not in out
    assert out["completedBatches"] == 1
    assert out["nodes"] == _ids("n", MAX_INSTANCE_WRITE_BATCH)
    assert out["edges"] == []


def test_delete_instances_chunks_dry_run_retrieve() -> None:
    client = MagicMock()
    client.data_modeling.instances.retrieve_nodes.return_value = []

    n = MAX_INSTANCE_WRITE_BATCH + 1
    items = [{"space": "sp_x", "externalId": f"n-{i}"} for i in range(n)]
    out = json.loads(delete_instances(client, items=items, dry_run=True))
    assert out["dryRun"] is True
    assert out["batches"] == 2
    assert client.data_modeling.instances.retrieve_nodes.call_count == 2


def test_delete_second_batch_failure_reports_completed_ids() -> None:
    client = MagicMock()
    client.data_modeling.instances.delete.side_effect = [
        SimpleNamespace(nodes=[], edges=[]),
        CogniteAPIError("delete failed", 500),
    ]
    n = MAX_INSTANCE_WRITE_BATCH + 3
    items = [{"space": "sp_x", "externalId": f"n-{i}"} for i in range(n)]
    out = json.loads(delete_instances(client, items=items, dry_run=False))
    assert out["error"] == "CogniteAPIError"
    assert out["code"] == 500
    assert "delete failed" in out["message"]
    assert out["completedBatches"] == 1
    assert out["items"] == _ids("n", MAX_INSTANCE_WRITE_BATCH)
    assert client.data_modeling.instances.delete.call_count == 2
