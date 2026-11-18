"""Unit tests for container / view / data model apply tools."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from cognite.client.data_classes.data_modeling import ContainerId, DataModelId, ViewId
from cognite.client.exceptions import CogniteAPIError

from cognite_cdf_mcp.tools.apply_containers import apply_containers
from cognite_cdf_mcp.tools.apply_data_models import apply_data_models
from cognite_cdf_mcp.tools.apply_views import apply_views
from cognite_cdf_mcp.tools.delete_container_indexes import delete_container_indexes
from cognite_cdf_mcp.tools.delete_containers import delete_containers
from cognite_cdf_mcp.tools.delete_data_models import delete_data_models
from cognite_cdf_mcp.tools.params import (
    MAX_CONTAINER_INDEX_DELETE,
    MAX_INDEXES_PER_CONTAINER,
    MAX_SCHEMA_PER_REQUEST,
)


def _container(external_id: str, *, with_index: bool = False) -> dict[str, Any]:
    body: dict[str, Any] = {
        "space": "sp_x",
        "externalId": external_id,
        "usedFor": "node",
        "properties": {
            "name": {"type": {"type": "text", "list": False}, "nullable": True},
        },
    }
    if with_index:
        body["indexes"] = {
            "nameIndex": {"indexType": "btree", "properties": ["name"]},
        }
    return body


def _view(external_id: str, version: str = "v1") -> dict[str, Any]:
    return {
        "space": "sp_x",
        "externalId": external_id,
        "version": version,
        "properties": {
            "name": {
                "container": {"space": "sp_x", "externalId": external_id},
                "containerPropertyIdentifier": "name",
            }
        },
    }


def _data_model(external_id: str, version: str = "v1") -> dict[str, Any]:
    return {
        "space": "sp_x",
        "externalId": external_id,
        "version": version,
        "views": [{"space": "sp_x", "externalId": "Asset", "version": "v1"}],
    }


def _schema_obj(space: str, external_id: str, version: str | None = None) -> SimpleNamespace:
    obj = SimpleNamespace(
        space=space,
        external_id=external_id,
        version=version,
        name=None,
        description=None,
    )

    def dump(camel_case: bool = False) -> dict[str, Any]:
        del camel_case
        body: dict[str, Any] = {"space": space, "externalId": external_id}
        if version is not None:
            body["version"] = version
        return body

    obj.dump = dump  # type: ignore[attr-defined]
    return obj


def test_apply_containers_chunks_at_100() -> None:
    client = MagicMock()
    client.data_modeling.containers.apply.side_effect = lambda items: [
        _schema_obj(item.space, item.external_id) for item in items
    ]
    count = MAX_SCHEMA_PER_REQUEST + 1
    out = json.loads(
        apply_containers(
            client,
            containers=[_container(f"c-{i}") for i in range(count)],
            dry_run=False,
        )
    )
    assert out["applied"] is True
    assert out["count"] == count
    assert out["batches"] == 2
    assert client.data_modeling.containers.apply.call_count == 2
    first = client.data_modeling.containers.apply.call_args_list[0].args[0]
    second = client.data_modeling.containers.apply.call_args_list[1].args[0]
    assert len(first) == MAX_SCHEMA_PER_REQUEST
    assert len(second) == 1


def test_apply_containers_later_batch_reports_completed_ids() -> None:
    client = MagicMock()
    client.data_modeling.containers.apply.side_effect = [
        [_schema_obj("sp_x", f"c-{i}") for i in range(MAX_SCHEMA_PER_REQUEST)],
        CogniteAPIError("apply failed", 400),
    ]
    out = json.loads(
        apply_containers(
            client,
            containers=[_container(f"c-{i}") for i in range(MAX_SCHEMA_PER_REQUEST + 1)],
            dry_run=False,
        )
    )
    assert out["error"] == "CogniteAPIError"
    assert out["completedBatches"] == 1
    assert out["items"] == [
        {"space": "sp_x", "externalId": f"c-{i}"} for i in range(MAX_SCHEMA_PER_REQUEST)
    ]


def test_apply_views_dry_run_retrieves_and_skips_write() -> None:
    client = MagicMock()
    client.data_modeling.views.retrieve.return_value = []
    client.iam.token.inspect.return_value = SimpleNamespace(capabilities=[])
    out = json.loads(apply_views(client, views=[_view("Asset")], dry_run=True))
    assert out["dryRun"] is True
    assert out["requested"] == 1
    assert out["payload"][0]["externalId"] == "Asset"
    assert client.data_modeling.views.apply.call_count == 0
    ids = client.data_modeling.views.retrieve.call_args.kwargs["ids"]
    assert ids[0].space == "sp_x"
    assert ids[0].external_id == "Asset"
    assert ids[0].version == "v1"


def test_apply_views_chunks_and_applies() -> None:
    client = MagicMock()
    client.data_modeling.views.apply.side_effect = lambda items: [
        _schema_obj(item.space, item.external_id, item.version) for item in items
    ]
    out = json.loads(
        apply_views(
            client,
            views=[_view(f"v-{i}") for i in range(MAX_SCHEMA_PER_REQUEST + 2)],
            dry_run=False,
        )
    )
    assert out["applied"] is True
    assert out["batches"] == 2
    assert client.data_modeling.views.apply.call_count == 2


def test_apply_data_models_keeps_bare_view_refs() -> None:
    client = MagicMock()

    def _apply(items: list[Any]) -> list[Any]:
        model = items[0]
        assert len(model.views) == 1
        assert isinstance(model.views[0], ViewId)
        return [_schema_obj(model.space, model.external_id, model.version)]

    client.data_modeling.data_models.apply.side_effect = _apply
    out = json.loads(apply_data_models(client, data_models=[_data_model("Plant")], dry_run=False))
    assert out["applied"] is True
    assert out["items"][0]["externalId"] == "Plant"


def test_apply_data_models_rejects_incomplete_view_ref() -> None:
    out = json.loads(
        apply_data_models(
            client=MagicMock(),
            data_models=[
                {
                    "space": "sp_x",
                    "externalId": "Plant",
                    "version": "v1",
                    "views": [{"space": "sp_x", "externalId": "Asset"}],
                }
            ],
            dry_run=False,
        )
    )
    assert out["error"] == "InvalidArgument"
    assert "version" in out["message"]


def test_apply_containers_invalid_payload() -> None:
    out = json.loads(apply_containers(MagicMock(), containers=[{"space": "sp_x"}], dry_run=True))
    assert out["error"] == "InvalidArgument"


def test_apply_containers_creates_indexes_via_payload() -> None:
    client = MagicMock()

    def _apply(items: list[Any]) -> list[Any]:
        assert "nameIndex" in items[0].indexes
        return [_schema_obj(items[0].space, items[0].external_id)]

    client.data_modeling.containers.apply.side_effect = _apply
    out = json.loads(
        apply_containers(client, containers=[_container("Asset", with_index=True)], dry_run=False)
    )
    assert out["applied"] is True

    client.iam.token.inspect.return_value = SimpleNamespace(capabilities=[])
    client.data_modeling.containers.retrieve.return_value = []
    preview = json.loads(
        apply_containers(client, containers=[_container("Asset", with_index=True)], dry_run=True)
    )
    assert "nameIndex" in preview["payload"][0]["indexes"]
    assert client.data_modeling.containers.apply.call_count == 1


def test_delete_container_indexes_chunks_at_10() -> None:
    client = MagicMock()
    existing = _schema_obj("sp_x", "Asset")
    existing.indexes = {f"idx-{i}": object() for i in range(MAX_CONTAINER_INDEX_DELETE + 1)}
    client.data_modeling.containers.retrieve.return_value = [existing]
    client.data_modeling.containers.delete_indexes.side_effect = lambda ids: list(ids)
    items = [
        {
            "space": "sp_x",
            "containerExternalId": "Asset",
            "identifier": f"idx-{i}",
        }
        for i in range(MAX_CONTAINER_INDEX_DELETE + 1)
    ]
    out = json.loads(delete_container_indexes(client, indexes=items, dry_run=False))
    assert out["deleted"] is True
    assert out["batches"] == 2
    assert client.data_modeling.containers.delete_indexes.call_count == 2
    first = client.data_modeling.containers.delete_indexes.call_args_list[0].args[0]
    second = client.data_modeling.containers.delete_indexes.call_args_list[1].args[0]
    assert len(first) == MAX_CONTAINER_INDEX_DELETE
    assert len(second) == 1
    assert first[0] == (ContainerId("sp_x", "Asset"), "idx-0")


def test_delete_container_indexes_dry_run_reports_found_and_missing() -> None:
    client = MagicMock()
    existing = _schema_obj("sp_x", "Asset")
    existing.indexes = {"nameIndex": object()}
    client.data_modeling.containers.retrieve.return_value = [existing]
    client.iam.token.inspect.return_value = SimpleNamespace(capabilities=[])
    out = json.loads(
        delete_container_indexes(
            client,
            indexes=[
                {
                    "space": "sp_x",
                    "externalId": "Asset",
                    "index": "nameIndex",
                },
                {
                    "space": "sp_x",
                    "containerExternalId": "Asset",
                    "identifier": "gone",
                },
            ],
            dry_run=True,
        )
    )
    assert out["dryRun"] is True
    assert out["found"] == 1
    assert out["items"] == [
        {"space": "sp_x", "containerExternalId": "Asset", "identifier": "nameIndex"}
    ]
    assert out["missing"] == [
        {"space": "sp_x", "containerExternalId": "Asset", "identifier": "gone"}
    ]
    assert client.data_modeling.containers.delete_indexes.call_count == 0


def test_delete_container_indexes_later_batch_reports_completed_ids() -> None:
    client = MagicMock()
    existing = _schema_obj("sp_x", "Asset")
    existing.indexes = {f"idx-{i}": object() for i in range(MAX_CONTAINER_INDEX_DELETE + 1)}
    client.data_modeling.containers.retrieve.return_value = [existing]
    client.data_modeling.containers.delete_indexes.side_effect = [
        [(ContainerId("sp_x", "Asset"), f"idx-{i}") for i in range(MAX_CONTAINER_INDEX_DELETE)],
        CogniteAPIError("delete failed", 400),
    ]
    items = [
        {
            "space": "sp_x",
            "containerExternalId": "Asset",
            "identifier": f"idx-{i}",
        }
        for i in range(MAX_CONTAINER_INDEX_DELETE + 1)
    ]
    out = json.loads(delete_container_indexes(client, indexes=items, dry_run=False))
    assert out["error"] == "CogniteAPIError"
    assert out["completedBatches"] == 1
    assert len(out["items"]) == MAX_CONTAINER_INDEX_DELETE


def test_delete_containers_chunks_at_100() -> None:
    client = MagicMock()
    client.data_modeling.containers.retrieve.side_effect = lambda ids: [
        _schema_obj(item.space, item.external_id) for item in ids
    ]
    client.data_modeling.containers.delete.side_effect = lambda ids: list(ids)
    items = [{"space": "sp_x", "externalId": f"c-{i}"} for i in range(MAX_SCHEMA_PER_REQUEST + 1)]
    out = json.loads(delete_containers(client, containers=items, dry_run=False))
    assert out["deleted"] is True
    assert out["batches"] == 2
    assert client.data_modeling.containers.delete.call_count == 2
    first = client.data_modeling.containers.delete.call_args_list[0].kwargs["ids"]
    second = client.data_modeling.containers.delete.call_args_list[1].kwargs["ids"]
    assert len(first) == MAX_SCHEMA_PER_REQUEST
    assert len(second) == 1
    assert first[0] == ContainerId("sp_x", "c-0")


def test_delete_containers_dry_run_reports_missing() -> None:
    client = MagicMock()
    client.data_modeling.containers.retrieve.return_value = [_schema_obj("sp_x", "Asset")]
    client.iam.token.inspect.return_value = SimpleNamespace(capabilities=[])
    out = json.loads(
        delete_containers(
            client,
            containers=[
                {"space": "sp_x", "externalId": "Asset"},
                {"space": "sp_x", "externalId": "Missing"},
            ],
            dry_run=True,
        )
    )
    assert out["dryRun"] is True
    assert out["found"] == 1
    assert out["missing"] == [{"space": "sp_x", "externalId": "Missing"}]
    assert client.data_modeling.containers.delete.call_count == 0


def test_delete_containers_later_batch_reports_completed_ids() -> None:
    client = MagicMock()
    client.data_modeling.containers.retrieve.side_effect = lambda ids: [
        _schema_obj(item.space, item.external_id) for item in ids
    ]
    client.data_modeling.containers.delete.side_effect = [
        [ContainerId("sp_x", f"c-{i}") for i in range(MAX_SCHEMA_PER_REQUEST)],
        CogniteAPIError("delete failed", 400),
    ]
    items = [{"space": "sp_x", "externalId": f"c-{i}"} for i in range(MAX_SCHEMA_PER_REQUEST + 1)]
    out = json.loads(delete_containers(client, containers=items, dry_run=False))
    assert out["error"] == "CogniteAPIError"
    assert out["completedBatches"] == 1
    assert len(out["items"]) == MAX_SCHEMA_PER_REQUEST


def test_delete_containers_skips_missing_on_real_delete() -> None:
    client = MagicMock()
    client.data_modeling.containers.retrieve.return_value = [_schema_obj("sp_x", "Asset")]
    client.data_modeling.containers.delete.side_effect = lambda ids: list(ids)
    out = json.loads(
        delete_containers(
            client,
            containers=[
                {"space": "sp_x", "externalId": "Asset"},
                {"space": "sp_x", "externalId": "Missing"},
            ],
            dry_run=False,
        )
    )
    assert out["deleted"] is True
    assert out["count"] == 1
    assert out["items"] == [{"space": "sp_x", "externalId": "Asset"}]
    assert out["missing"] == [{"space": "sp_x", "externalId": "Missing"}]
    deleted_ids = client.data_modeling.containers.delete.call_args.kwargs["ids"]
    assert deleted_ids == [ContainerId("sp_x", "Asset")]


def test_delete_data_models_skips_missing_on_real_delete() -> None:
    client = MagicMock()
    client.data_modeling.data_models.retrieve.return_value = [
        _schema_obj("sp_x", "Plant", version="v1")
    ]
    client.data_modeling.data_models.delete.side_effect = lambda ids: list(ids)
    out = json.loads(
        delete_data_models(
            client,
            data_models=[
                {"space": "sp_x", "externalId": "Plant", "version": "v1"},
                {"space": "sp_x", "externalId": "Missing", "version": "v1"},
            ],
            dry_run=False,
        )
    )
    assert out["deleted"] is True
    assert out["count"] == 1
    assert out["items"] == [{"space": "sp_x", "externalId": "Plant", "version": "v1"}]
    assert out["missing"] == [{"space": "sp_x", "externalId": "Missing", "version": "v1"}]
    deleted_ids = client.data_modeling.data_models.delete.call_args.kwargs["ids"]
    assert deleted_ids == [DataModelId("sp_x", "Plant", "v1")]


def test_delete_container_indexes_skips_missing_on_real_delete() -> None:
    client = MagicMock()
    existing = _schema_obj("sp_x", "Asset")
    existing.indexes = {"nameIndex": object()}
    client.data_modeling.containers.retrieve.return_value = [existing]
    client.data_modeling.containers.delete_indexes.side_effect = lambda ids: list(ids)
    out = json.loads(
        delete_container_indexes(
            client,
            indexes=[
                {
                    "space": "sp_x",
                    "containerExternalId": "Asset",
                    "identifier": "nameIndex",
                },
                {
                    "space": "sp_x",
                    "containerExternalId": "Asset",
                    "identifier": "gone",
                },
            ],
            dry_run=False,
        )
    )
    assert out["deleted"] is True
    assert out["count"] == 1
    assert out["items"] == [
        {"space": "sp_x", "containerExternalId": "Asset", "identifier": "nameIndex"}
    ]
    assert out["missing"] == [
        {"space": "sp_x", "containerExternalId": "Asset", "identifier": "gone"}
    ]
    deleted = client.data_modeling.containers.delete_indexes.call_args.args[0]
    assert deleted == [(ContainerId("sp_x", "Asset"), "nameIndex")]


def test_delete_data_models_chunks_at_100() -> None:
    client = MagicMock()
    client.data_modeling.data_models.retrieve.side_effect = lambda ids, inline_views=False: [
        _schema_obj(item.space, item.external_id, version=item.version) for item in ids
    ]
    client.data_modeling.data_models.delete.side_effect = lambda ids: list(ids)
    items = [
        {"space": "sp_x", "externalId": f"m-{i}", "version": "v1"}
        for i in range(MAX_SCHEMA_PER_REQUEST + 1)
    ]
    out = json.loads(delete_data_models(client, data_models=items, dry_run=False))
    assert out["deleted"] is True
    assert out["batches"] == 2
    assert client.data_modeling.data_models.delete.call_count == 2
    first = client.data_modeling.data_models.delete.call_args_list[0].kwargs["ids"]
    second = client.data_modeling.data_models.delete.call_args_list[1].kwargs["ids"]
    assert len(first) == MAX_SCHEMA_PER_REQUEST
    assert len(second) == 1
    assert first[0] == DataModelId("sp_x", "m-0", "v1")


def test_delete_data_models_dry_run_reports_missing() -> None:
    client = MagicMock()
    client.data_modeling.data_models.retrieve.return_value = [
        _schema_obj("sp_x", "Plant", version="v1")
    ]
    client.iam.token.inspect.return_value = SimpleNamespace(capabilities=[])
    out = json.loads(
        delete_data_models(
            client,
            data_models=[
                {"space": "sp_x", "externalId": "Plant", "version": "v1"},
                {"space": "sp_x", "externalId": "Missing", "version": "v1"},
            ],
            dry_run=True,
        )
    )
    assert out["dryRun"] is True
    assert out["found"] == 1
    assert out["missing"] == [{"space": "sp_x", "externalId": "Missing", "version": "v1"}]
    assert "Referenced views are not deleted" in out["message"]
    assert client.data_modeling.data_models.delete.call_count == 0


def test_delete_data_models_rejects_incomplete_id() -> None:
    out = json.loads(
        delete_data_models(
            MagicMock(),
            data_models=[{"space": "sp_x", "externalId": "Plant"}],
            dry_run=True,
        )
    )
    assert out["error"] == "InvalidArgument"
    assert "version" in out["message"]


def test_apply_containers_rejects_too_many_indexes() -> None:
    indexes = {
        f"idx-{i}": {"indexType": "btree", "properties": ["name"]}
        for i in range(MAX_INDEXES_PER_CONTAINER + 1)
    }
    out = json.loads(
        apply_containers(
            MagicMock(),
            containers=[
                {
                    "space": "sp_x",
                    "externalId": "Asset",
                    "usedFor": "node",
                    "properties": {
                        "name": {"type": {"type": "text", "list": False}, "nullable": True},
                    },
                    "indexes": indexes,
                }
            ],
            dry_run=True,
        )
    )
    assert out["error"] == "InvalidArgument"
    assert str(MAX_INDEXES_PER_CONTAINER) in out["message"]


def test_apply_views_record_view_uses_stream_id() -> None:
    client = MagicMock()
    client.data_modeling.views.apply.side_effect = lambda items: [
        _schema_obj(item.space, item.external_id, version=item.version) for item in items
    ]
    out = json.loads(
        apply_views(
            client,
            views=[
                {
                    "space": "sp_x",
                    "externalId": "Rec",
                    "version": "v1",
                    "streamId": "stream-1",
                    "properties": {},
                }
            ],
            dry_run=False,
        )
    )
    assert out["applied"] is True
    applied = client.data_modeling.views.apply.call_args.args[0]
    assert len(applied) == 1
    assert type(applied[0]).__name__ == "RecordViewApply"
    assert getattr(applied[0], "stream_id", None) or applied[0].dump(camel_case=True).get(
        "streamId"
    )


def test_delete_containers_partial_403_includes_access() -> None:
    client = MagicMock()
    client.data_modeling.containers.retrieve.side_effect = lambda ids: [
        _schema_obj(item.space, item.external_id) for item in ids
    ]
    client.data_modeling.containers.delete.side_effect = [
        [ContainerId("sp_x", f"c-{i}") for i in range(MAX_SCHEMA_PER_REQUEST)],
        CogniteAPIError("forbidden", 403),
    ]
    client.iam.token.inspect.return_value = SimpleNamespace(capabilities=[])
    items = [{"space": "sp_x", "externalId": f"c-{i}"} for i in range(MAX_SCHEMA_PER_REQUEST + 1)]
    out = json.loads(delete_containers(client, containers=items, dry_run=False))
    assert out["error"] == "CogniteAPIError"
    assert out["code"] == 403
    assert out["completedBatches"] == 1
    assert out["access"]["allowed"] is False
    assert "sp_x" in out["access"]["missingSpaces"]


def test_apply_containers_partial_403_includes_access() -> None:
    client = MagicMock()
    client.data_modeling.containers.apply.side_effect = [
        [_schema_obj("sp_x", f"c-{i}") for i in range(MAX_SCHEMA_PER_REQUEST)],
        CogniteAPIError("forbidden", 403),
    ]
    client.iam.token.inspect.return_value = SimpleNamespace(capabilities=[])
    out = json.loads(
        apply_containers(
            client,
            containers=[_container(f"c-{i}") for i in range(MAX_SCHEMA_PER_REQUEST + 1)],
            dry_run=False,
        )
    )
    assert out["error"] == "CogniteAPIError"
    assert out["code"] == 403
    assert out["completedBatches"] == 1
    assert out["access"]["allowed"] is False
    assert "sp_x" in out["access"]["missingSpaces"]
