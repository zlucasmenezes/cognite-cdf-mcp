"""Unit tests: apply/delete chunk at MAX_INSTANCE_WRITE_BATCH."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

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


def test_delete_instances_chunks_dry_run_retrieve() -> None:
    client = MagicMock()
    client.data_modeling.instances.retrieve_nodes.return_value = []

    n = MAX_INSTANCE_WRITE_BATCH + 1
    items = [{"space": "sp_x", "externalId": f"n-{i}"} for i in range(n)]
    out = json.loads(delete_instances(client, items=items, dry_run=True))
    assert out["dryRun"] is True
    assert out["batches"] == 2
    assert client.data_modeling.instances.retrieve_nodes.call_count == 2
