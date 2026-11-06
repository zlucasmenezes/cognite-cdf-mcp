"""Unit tests: token access summary."""

from __future__ import annotations

import json
from collections import UserList
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from cognite_cdf_mcp.tools.access import get_access


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
