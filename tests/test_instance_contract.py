"""Unit tests for delete response shape and instance dry-run preview."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from cognite_cdf_mcp.tools.apply_instances import apply_instances
from cognite_cdf_mcp.tools.delete_instances import delete_instances


def _node(external_id: str, view: str = "CogniteAsset") -> dict[str, object]:
    return {
        "space": "sp_x",
        "externalId": external_id,
        "viewSpace": "cdf_cdm",
        "viewExternalId": view,
        "viewVersion": "v1",
        "properties": {"name": external_id},
    }


def _existing(external_id: str, **properties: str) -> SimpleNamespace:
    node = SimpleNamespace(space="sp_x", external_id=external_id)

    def dump(camel_case: bool = False) -> dict[str, object]:
        del camel_case
        return {
            "space": "sp_x",
            "externalId": external_id,
            "properties": dict(properties),
        }

    node.dump = dump
    return node


def test_delete_instances_returns_nodes_and_edges() -> None:
    client = MagicMock()
    client.data_modeling.instances.delete.return_value = SimpleNamespace(
        nodes=[SimpleNamespace(space="sp", external_id="n1")],
        edges=[SimpleNamespace(space="sp", external_id="e1")],
    )
    out = json.loads(
        delete_instances(
            client,
            items=[{"space": "sp", "externalId": "n1"}],
            dry_run=False,
        )
    )
    assert out["deleted"] is True
    assert out["count"] == 2
    assert out["nodes"] == [{"space": "sp", "externalId": "n1"}]
    assert out["edges"] == [{"space": "sp", "externalId": "e1"}]
    assert out["items"] == out["nodes"] + out["edges"]


def test_delete_edge_only_still_returns_edges() -> None:
    client = MagicMock()
    client.data_modeling.instances.delete.return_value = SimpleNamespace(
        nodes=[],
        edges=[SimpleNamespace(space="sp", external_id="e1")],
    )
    out = json.loads(
        delete_instances(
            client,
            items=[{"space": "sp", "externalId": "e1"}],
            instance_type="edge",
            dry_run=False,
        )
    )
    assert out["nodes"] == []
    assert out["edges"] == [{"space": "sp", "externalId": "e1"}]
    assert out["items"] == out["edges"]


def test_apply_dry_run_passes_view_and_keeps_properties() -> None:
    client = MagicMock()
    client.data_modeling.instances.retrieve_nodes.return_value = [_existing("MCH-1", name="Pump")]
    client.data_modeling.instances.retrieve_edges.return_value = []
    out = json.loads(apply_instances(client, nodes=[_node("MCH-1")], dry_run=True))
    sources = client.data_modeling.instances.retrieve_nodes.call_args.kwargs["sources"]
    assert sources[0].space == "cdf_cdm"
    assert sources[0].external_id == "CogniteAsset"
    assert sources[0].version == "v1"
    assert out["nodes"]["existing"][0]["properties"] == {"name": "Pump"}
    assert out["nodes"]["payload"][0]["sources"][0]["properties"] == {"name": "MCH-1"}
    assert client.data_modeling.instances.apply.call_count == 0


def _cdf_sources_node(
    external_id: str,
    *,
    source_type: str = "view",
    start_time: str = "05:30:00",
) -> dict[str, object]:
    source: dict[str, object] = {
        "type": source_type,
        "space": "sp_views" if source_type == "view" else "sp_containers",
        "externalId": "Asset",
    }
    if source_type == "view":
        source["version"] = "v1"
    return {
        "space": "sp_data",
        "externalId": external_id,
        "instanceType": "node",
        "sources": [{"source": source, "properties": {"startTime": start_time}}],
    }


def test_apply_accepts_cdf_sources_view_payload() -> None:
    client = MagicMock()
    client.data_modeling.instances.retrieve_nodes.return_value = []
    out = json.loads(apply_instances(client, nodes=[_cdf_sources_node("NODE-1")], dry_run=True))
    payload = out["nodes"]["payload"][0]
    assert payload["sources"][0]["properties"] == {"startTime": "05:30:00"}
    assert payload["sources"][0]["source"] == {
        "space": "sp_views",
        "externalId": "Asset",
        "version": "v1",
        "type": "view",
    }
    sources = client.data_modeling.instances.retrieve_nodes.call_args.kwargs["sources"]
    assert sources[0].space == "sp_views"
    assert sources[0].external_id == "Asset"
    assert sources[0].version == "v1"


def test_apply_accepts_cdf_sources_container_payload() -> None:
    client = MagicMock()
    client.data_modeling.instances.apply.return_value = SimpleNamespace(nodes=[], edges=[])
    out = json.loads(
        apply_instances(
            client,
            nodes=[_cdf_sources_node("NODE-1", source_type="container")],
            dry_run=False,
        )
    )
    assert out["applied"] is True
    applied = client.data_modeling.instances.apply.call_args.kwargs["nodes"][0]
    assert applied.sources[0].properties == {"startTime": "05:30:00"}
    assert applied.sources[0].source.space == "sp_containers"
    assert applied.sources[0].source.external_id == "Asset"


def test_apply_rejects_empty_sources() -> None:
    out = json.loads(
        apply_instances(
            client=MagicMock(),
            nodes=[{"space": "sp_x", "externalId": "n1", "sources": []}],
            dry_run=True,
        )
    )
    assert out["error"] == "InvalidArgument"
    assert "non-empty" in out["message"]


def test_apply_rejects_sources_mixed_with_flat_fields() -> None:
    out = json.loads(
        apply_instances(
            client=MagicMock(),
            nodes=[
                {
                    **_cdf_sources_node("NODE-1"),
                    "viewSpace": "sp_views",
                    "viewExternalId": "Asset",
                    "viewVersion": "v1",
                    "properties": {"startTime": "05:30:00"},
                }
            ],
            dry_run=True,
        )
    )
    assert out["error"] == "InvalidArgument"
    assert "cannot combine sources" in out["message"]


def test_apply_rejects_sources_view_without_version() -> None:
    out = json.loads(
        apply_instances(
            client=MagicMock(),
            nodes=[
                {
                    "space": "sp_x",
                    "externalId": "n1",
                    "sources": [
                        {
                            "source": {
                                "type": "view",
                                "space": "cdf_cdm",
                                "externalId": "CogniteAsset",
                            },
                            "properties": {"name": "x"},
                        }
                    ],
                }
            ],
            dry_run=True,
        )
    )
    assert out["error"] == "InvalidArgument"
    assert "version" in out["message"]


def test_apply_dry_run_groups_distinct_views() -> None:
    client = MagicMock()
    client.data_modeling.instances.retrieve_nodes.return_value = []
    apply_instances(
        client,
        nodes=[
            _node("a", view="Asset"),
            _node("b", view="Equipment"),
            {"space": "sp_x", "externalId": "plain"},
        ],
        dry_run=True,
    )
    calls = client.data_modeling.instances.retrieve_nodes.call_args_list
    assert len(calls) == 3
    requested = []
    for call in calls:
        sources = call.kwargs["sources"]
        requested.append(None if sources is None else sources[0].external_id)
    assert requested == ["Asset", "Equipment", None]


def test_apply_dry_run_does_not_simulate_replace() -> None:
    client = MagicMock()
    client.data_modeling.instances.retrieve_nodes.return_value = [
        _existing("MCH-1", name="Pump", status="on")
    ]
    out = json.loads(apply_instances(client, nodes=[_node("MCH-1")], replace=True, dry_run=True))
    assert out["replace"] is True
    assert "not simulated" in out["message"]
    assert out["nodes"]["existing"][0]["properties"] == {"name": "Pump", "status": "on"}
    assert client.data_modeling.instances.apply.call_count == 0


def test_delete_node_dry_run_warns_about_edge_cascade() -> None:
    client = MagicMock()
    client.data_modeling.instances.retrieve_nodes.return_value = []
    out = json.loads(
        delete_instances(
            client,
            items=[{"space": "sp", "externalId": "n1"}],
            dry_run=True,
        )
    )
    assert "start or end on it" in out["message"]
    assert "Too many connected edges" in out["message"]
    assert client.data_modeling.instances.retrieve_nodes.call_args.kwargs["sources"] is None
    assert client.data_modeling.instances.delete.call_count == 0


def test_delete_edge_dry_run_does_not_warn_about_node_cascade() -> None:
    client = MagicMock()
    client.data_modeling.instances.retrieve_edges.return_value = []
    out = json.loads(
        delete_instances(
            client,
            items=[{"space": "sp", "externalId": "e1"}],
            instance_type="edge",
            dry_run=True,
        )
    )
    assert "start or end" not in out["message"]
    assert "Missing ids are omitted from items." in out["message"]


def test_delete_dry_run_passes_view_when_supplied() -> None:
    client = MagicMock()
    client.data_modeling.instances.retrieve_nodes.return_value = []
    delete_instances(
        client,
        items=[
            {
                "space": "sp",
                "externalId": "n1",
                "viewSpace": "cdf_cdm",
                "viewExternalId": "CogniteAsset",
                "viewVersion": "v1",
            }
        ],
        dry_run=True,
    )
    sources = client.data_modeling.instances.retrieve_nodes.call_args.kwargs["sources"]
    assert sources[0].space == "cdf_cdm"
    assert sources[0].external_id == "CogniteAsset"
    assert sources[0].version == "v1"
