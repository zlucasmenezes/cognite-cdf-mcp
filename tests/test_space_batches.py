"""Unit tests: space apply/delete stay within the 100-id CDF cap."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.apply_spaces import apply_spaces
from cognite_cdf_mcp.tools.delete_spaces import delete_spaces
from cognite_cdf_mcp.tools.params import MAX_SPACES_PER_REQUEST


def _space_items(count: int) -> list[dict[str, str]]:
    return [{"space": f"s-{i}"} for i in range(count)]


def _space_obj(space_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        space=space_id,
        name=None,
        description=None,
        is_global=None,
        created_time=None,
        last_updated_time=None,
    )


def test_apply_spaces_chunks_at_100() -> None:
    client = MagicMock()
    client.data_modeling.spaces.apply.side_effect = lambda spaces: [
        _space_obj(item.space) for item in spaces
    ]

    count = MAX_SPACES_PER_REQUEST + 1
    out = json.loads(apply_spaces(client, spaces=_space_items(count), dry_run=False))
    assert out["applied"] is True
    assert out["count"] == count
    assert [item["space"] for item in out["items"]] == [f"s-{i}" for i in range(count)]
    assert client.data_modeling.spaces.apply.call_count == 2
    first = client.data_modeling.spaces.apply.call_args_list[0].args[0]
    second = client.data_modeling.spaces.apply.call_args_list[1].args[0]
    assert len(first) == MAX_SPACES_PER_REQUEST
    assert len(second) == 1


def test_apply_spaces_one_batch_when_at_cap() -> None:
    client = MagicMock()
    client.data_modeling.spaces.apply.return_value = [
        _space_obj(f"s-{i}") for i in range(MAX_SPACES_PER_REQUEST)
    ]
    out = json.loads(
        apply_spaces(client, spaces=_space_items(MAX_SPACES_PER_REQUEST), dry_run=False)
    )
    assert out["count"] == MAX_SPACES_PER_REQUEST
    assert client.data_modeling.spaces.apply.call_count == 1


def test_apply_spaces_later_batch_reports_completed_ids() -> None:
    client = MagicMock()
    client.data_modeling.spaces.apply.side_effect = [
        [_space_obj(f"s-{i}") for i in range(MAX_SPACES_PER_REQUEST)],
        CogniteAPIError("apply failed", 400),
    ]
    out = json.loads(
        apply_spaces(
            client,
            spaces=_space_items(MAX_SPACES_PER_REQUEST + 1),
            dry_run=False,
        )
    )
    assert out["error"] == "CogniteAPIError"
    assert out["code"] == 400
    assert "apply failed" in out["message"]
    assert out["completedBatches"] == 1
    assert out["items"] == [{"space": f"s-{i}"} for i in range(MAX_SPACES_PER_REQUEST)]
    assert client.data_modeling.spaces.apply.call_count == 2


def test_apply_spaces_first_batch_failure_has_no_completed_ids() -> None:
    client = MagicMock()
    client.data_modeling.spaces.apply.side_effect = CogniteException("connection reset")
    out = json.loads(apply_spaces(client, spaces=_space_items(2), dry_run=False))
    assert out["error"] == "CogniteException"
    assert "connection reset" in out["message"]
    assert "completedBatches" not in out
    assert "items" not in out


def test_apply_spaces_dry_run_chunks_retrieve() -> None:
    client = MagicMock()

    def _retrieve(spaces: list[str]) -> list[Any]:
        return [_space_obj(space_id) for space_id in spaces]

    client.data_modeling.spaces.retrieve.side_effect = _retrieve
    count = MAX_SPACES_PER_REQUEST + 5
    out = json.loads(apply_spaces(client, spaces=_space_items(count), dry_run=True))
    assert out["dryRun"] is True
    assert out["alreadyExist"] == count
    assert client.data_modeling.spaces.retrieve.call_count == 2
    assert client.data_modeling.spaces.apply.call_count == 0
    first = client.data_modeling.spaces.retrieve.call_args_list[0].kwargs["spaces"]
    assert len(first) == MAX_SPACES_PER_REQUEST


def test_delete_spaces_chunks_and_reports_later_failure() -> None:
    client = MagicMock()
    client.data_modeling.spaces.delete.side_effect = [
        [f"s-{i}" for i in range(MAX_SPACES_PER_REQUEST)],
        CogniteAPIError("delete failed", 409),
    ]
    out = json.loads(
        delete_spaces(
            client,
            spaces=_space_items(MAX_SPACES_PER_REQUEST + 3),
            dry_run=False,
        )
    )
    assert out["error"] == "CogniteAPIError"
    assert out["code"] == 409
    assert out["completedBatches"] == 1
    assert out["items"] == [{"space": f"s-{i}"} for i in range(MAX_SPACES_PER_REQUEST)]
    assert client.data_modeling.spaces.delete.call_count == 2
    first = client.data_modeling.spaces.delete.call_args_list[0].kwargs["spaces"]
    assert len(first) == MAX_SPACES_PER_REQUEST


def test_delete_spaces_dry_run_keeps_dependency_warning_and_chunks() -> None:
    client = MagicMock()
    client.data_modeling.spaces.retrieve.return_value = []
    out = json.loads(
        delete_spaces(
            client,
            spaces=_space_items(MAX_SPACES_PER_REQUEST + 1),
            dry_run=True,
        )
    )
    assert out["dryRun"] is True
    assert "Dependency conflicts are not validated in dry run." in out["message"]
    assert client.data_modeling.spaces.retrieve.call_count == 2
    assert client.data_modeling.spaces.delete.call_count == 0
