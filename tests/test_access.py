"""Unit tests: token access summary and write dry-run denial."""

from __future__ import annotations

import json
from collections import UserList
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from cognite.client.exceptions import CogniteAPIError

from cognite_cdf_mcp.tools.access import get_access
from cognite_cdf_mcp.tools.apply_instances import apply_instances
from cognite_cdf_mcp.tools.apply_spaces import apply_spaces
from cognite_cdf_mcp.tools.delete_instances import delete_instances


def _cap(
    acl: str,
    actions: list[str],
    *,
    spaces: list[str] | None = None,
    all_spaces: bool = False,
    projects: list[str] | None = None,
) -> SimpleNamespace:
    if all_spaces:
        scope: dict[str, Any] = {"all": {}}
    else:
        scope = {"spaceIdScope": {"spaceIds": spaces or []}}
    dumped: dict[str, Any] = {acl: {"actions": actions, "scope": scope}}
    if projects is not None:
        dumped["projectScope"] = {"projects": projects}
    return SimpleNamespace(dump=lambda camel_case=True, payload=dumped: payload)


def _client(*caps: SimpleNamespace, project: str = "bdx-preprod") -> MagicMock:
    client = MagicMock()
    client.config.project = project
    client.iam.token.inspect.return_value = SimpleNamespace(capabilities=list(caps))
    return client


def test_get_access_accepts_sdk_capability_user_list() -> None:
    client = MagicMock()
    client.config.project = "bdx-dev"
    client.iam.token.inspect.return_value = SimpleNamespace(
        capabilities=UserList(
            [
                _cap(
                    "dataModelInstancesAcl",
                    ["READ", "WRITE"],
                    all_spaces=True,
                    projects=["bdx-dev"],
                )
            ]
        )
    )
    out = json.loads(get_access(client))
    assert out["project"] == "bdx-dev"
    assert out["dataModelInstancesAcl"]["READ"] == {"all": True, "spaces": []}
    assert out["dataModelInstancesAcl"]["WRITE"]["all"] is True


def test_get_access_space_booleans_ignore_other_projects() -> None:
    client = _client(
        _cap(
            "dataModelInstancesAcl",
            ["READ"],
            spaces=["sp_shf_fra_dat"],
            projects=["bdx-preprod"],
        ),
        _cap(
            "dataModelInstancesAcl",
            ["READ", "WRITE"],
            spaces=["sp_shf_fra_dat"],
            projects=["bdx-prod"],
        ),
        _cap(
            "dataModelsAcl",
            ["READ"],
            spaces=["sp_shf_glb_dmd"],
            projects=["bdx-preprod"],
        ),
    )
    out = json.loads(get_access(client, space="sp_shf_fra_dat"))
    assert out["project"] == "bdx-preprod"
    assert out["dataModelInstancesAcl"] == {"READ": True}
    assert out["dataModelsAcl"] == {"READ": False}


def test_get_access_without_space_lists_write_spaces_and_extra_actions() -> None:
    client = _client(
        _cap(
            "dataModelInstancesAcl",
            ["READ", "WRITE_PROPERTIES"],
            spaces=["sp_shf_fra_dat", "sp_shf_san_dat"],
            projects=["bdx-preprod"],
        ),
        _cap(
            "dataModelInstancesAcl",
            ["WRITE"],
            all_spaces=True,
            projects=["bdx-preprod"],
        ),
    )
    out = json.loads(get_access(client, acl="dataModelInstancesAcl"))
    assert "dataModelsAcl" not in out
    instances = out["dataModelInstancesAcl"]
    assert instances["READ"] == {
        "all": False,
        "spaces": ["sp_shf_fra_dat", "sp_shf_san_dat"],
    }
    assert instances["WRITE"] == {"all": True, "spaces": []}
    assert instances["WRITE_PROPERTIES"]["spaces"] == ["sp_shf_fra_dat", "sp_shf_san_dat"]


def test_get_access_action_filter() -> None:
    client = _client(
        _cap("dataModelInstancesAcl", ["READ", "WRITE"], all_spaces=True, projects=["bdx-preprod"])
    )
    out = json.loads(get_access(client, space="sp_shf_fra_dat", action="write"))
    assert out["dataModelInstancesAcl"] == {"WRITE": True}
    assert "dataModelsAcl" not in out


def test_get_access_includes_non_modeling_capabilities() -> None:
    agents = _cap("agentsAcl", ["READ", "RUN"], all_spaces=True, projects=["bdx-dev"])
    assets = SimpleNamespace(
        dump=lambda camel_case=True: {
            "assetsAcl": {
                "actions": ["READ"],
                "scope": {"datasetScope": {"ids": [10]}},
            },
            "projectScope": {"projects": ["bdx-dev"]},
        }
    )
    client = _client(agents, assets, project="bdx-dev")
    out = json.loads(get_access(client))
    assert out["agentsAcl"]["RUN"] == {"all": True, "spaces": []}
    assert out["agentsAcl"]["READ"]["all"] is True
    assert "WRITE" not in out["agentsAcl"]
    assert out["assetsAcl"]["READ"]["scope"] == [{"datasetScope": {"ids": [10]}}]
    assert out["assetsAcl"]["READ"]["spaces"] == []


def test_apply_instances_dry_run_denies_missing_write() -> None:
    client = _client(
        _cap("dataModelInstancesAcl", ["READ"], spaces=["sp_shf_fra_dat"], projects=["bdx-preprod"])
    )
    client.data_modeling.instances.retrieve_nodes.return_value = []
    out = json.loads(
        apply_instances(
            client,
            nodes=[
                {
                    "space": "sp_shf_fra_dat",
                    "externalId": "SFT-Central-CEN",
                    "viewSpace": "sp_shf_glb_dmd",
                    "viewExternalId": "Shift",
                    "viewVersion": "v1.0.0",
                    "properties": {"name": "Central"},
                }
            ],
            dry_run=True,
        )
    )
    assert out["dryRun"] is True
    assert out["wouldApply"] is False
    assert out["access"]["allowed"] is False
    assert out["access"]["missingSpaces"] == ["sp_shf_fra_dat"]
    assert "WRITE" in out["message"]
    assert client.data_modeling.instances.apply.call_count == 0


def test_apply_instances_dry_run_allows_write() -> None:
    client = _client(
        _cap(
            "dataModelInstancesAcl",
            ["READ", "WRITE"],
            spaces=["sp_shf_fra_dat"],
            projects=["bdx-preprod"],
        )
    )
    client.data_modeling.instances.retrieve_nodes.return_value = []
    out = json.loads(
        apply_instances(
            client,
            nodes=[
                {
                    "space": "sp_shf_fra_dat",
                    "externalId": "SFT-Central-CEN",
                    "viewSpace": "sp_shf_glb_dmd",
                    "viewExternalId": "Shift",
                    "viewVersion": "v1.0.0",
                    "properties": {"name": "Central"},
                }
            ],
            dry_run=True,
        )
    )
    assert out["wouldApply"] is True
    assert out["access"]["allowed"] is True
    assert out["access"]["missingSpaces"] == []


def test_apply_instances_403_includes_access() -> None:
    client = _client(
        _cap("dataModelInstancesAcl", ["READ"], spaces=["sp_x"], projects=["bdx-preprod"])
    )
    client.data_modeling.instances.apply.side_effect = CogniteAPIError("forbidden", 403)
    out = json.loads(
        apply_instances(
            client,
            nodes=[
                {
                    "space": "sp_x",
                    "externalId": "n-1",
                    "viewSpace": "vs",
                    "viewExternalId": "V",
                    "viewVersion": "v1",
                    "properties": {"name": "N"},
                }
            ],
            dry_run=False,
        )
    )
    assert out["code"] == 403
    assert out["access"]["allowed"] is False
    assert out["access"]["missingSpaces"] == ["sp_x"]


def test_delete_instances_dry_run_denies_missing_write() -> None:
    client = _client(
        _cap("dataModelInstancesAcl", ["READ"], spaces=["sp_x"], projects=["bdx-preprod"])
    )
    client.data_modeling.instances.retrieve_nodes.return_value = [SimpleNamespace()]
    out = json.loads(
        delete_instances(
            client,
            items=[{"space": "sp_x", "externalId": "n-1"}],
            dry_run=True,
        )
    )
    assert out["found"] == 1
    assert out["wouldDelete"] is False
    assert out["access"]["missingSpaces"] == ["sp_x"]
    assert client.data_modeling.instances.delete.call_count == 0


def test_apply_spaces_dry_run_denies_missing_write() -> None:
    client = _client(_cap("dataModelsAcl", ["READ"], all_spaces=True, projects=["bdx-preprod"]))
    client.data_modeling.spaces.retrieve.return_value = []
    out = json.loads(
        apply_spaces(client, spaces=[{"space": "sp_new", "name": "New"}], dry_run=True)
    )
    assert out["wouldApply"] is False
    assert out["access"]["acl"] == "dataModelsAcl"
    assert out["access"]["missingSpaces"] == ["sp_new"]
    assert client.data_modeling.spaces.apply.call_count == 0
