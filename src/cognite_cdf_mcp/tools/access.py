"""Token capability summary for the current CDF project.

Uses ``client.iam.token.inspect()``. The bearer token itself is never returned.
Capabilities scoped to other projects are ignored.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from cognite.client import CogniteClient
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.params import optional_str

logger = logging.getLogger(__name__)

# Shown when the caller asks for one ACL, so a missing READ/WRITE is explicit.
# A call without ``acl`` returns every capability on the token instead.
COMMON_ACTIONS: tuple[str, ...] = ("READ", "WRITE")

INSTANCES_ACL = "dataModelInstancesAcl"
MODELS_ACL = "dataModelsAcl"


@dataclass(frozen=True)
class Grant:
    """Where one ACL action applies.

    ``all_spaces`` ignores ``spaces``. ``other_scopes`` keeps non-space scopes
    (dataset, ids, current user, and so on) so they are not reported as no access.
    """

    all_spaces: bool
    spaces: frozenset[str]
    other_scopes: tuple[dict[str, Any], ...] = ()


def get_access(
    client: CogniteClient,
    *,
    space: str | None = None,
    acl: str | None = None,
    action: str | None = None,
) -> str:
    """Summarize the current token's capabilities in this client project.

    Without ``acl``, every capability granted in the project is returned
    (for example ``agentsAcl`` with ``RUN``). ``acl`` limits the result to one
    capability and also reports missing ``READ``/``WRITE``.

    With ``space``, each action is a boolean for that space. ``all`` scopes
    count as covered. Scopes that are not space-based stay false here; call
    without ``space`` to see them.
    Without ``space``, each action lists ``all``, explicit space ids, and any
    other scope.
    """
    try:
        space_id = optional_str(space)
        acl_name = optional_str(acl)
        action_name = optional_str(action)
        if action_name is not None:
            action_name = action_name.upper()
        grants = load_grants(client)
        selected = (acl_name,) if acl_name else tuple(sorted(grants))
        project = _project(client)
        if space_id:
            body: dict[str, Any] = {"project": project, "space": space_id}
            for name in selected:
                body[name] = _booleans_for_space(
                    grants.get(name, {}),
                    space_id,
                    action_name,
                    include_common=acl_name is not None,
                )
        else:
            body = {"project": project}
            for name in selected:
                body[name] = _lists_for_acl(
                    grants.get(name, {}),
                    action_name,
                    include_common=acl_name is not None,
                )
        return json.dumps(body, indent=2)
    except (TypeError, ValueError) as exc:
        return json.dumps({"error": "InvalidArgument", "message": str(exc)})
    except CogniteAPIError as exc:
        logger.exception("CDF API error inspecting token access")
        return json.dumps(
            {
                "error": "CogniteAPIError",
                "code": getattr(exc, "code", None),
                "message": str(exc),
            }
        )
    except CogniteException as exc:
        logger.exception("Cognite error inspecting token access")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error inspecting token access")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})


def is_denied(access: dict[str, Any]) -> bool:
    """True only when the check ran and at least one space is missing the action."""
    return access.get("allowed") is False


def denial_detail(access: dict[str, Any]) -> str:
    """Short explanation for a denied ``check_spaces`` result."""
    missing = ", ".join(access.get("missingSpaces") or []) or "(none)"
    return f"Token lacks {access.get('acl')}:{access.get('action')} on: {missing}."


def check_spaces(
    client: CogniteClient,
    *,
    acl: str,
    action: str,
    spaces: list[str],
) -> dict[str, Any]:
    """Whether ``action`` on ``acl`` covers every space.

    Failures become ``{"error": "AccessUnknown", ...}`` so callers can still
    return their own result. ``allowed`` is present only when the check ran.
    """
    action_name = action.upper()
    unique = list(dict.fromkeys(spaces))
    try:
        grants = load_grants(client)
    except (CogniteAPIError, CogniteException, TypeError, ValueError) as exc:
        logger.exception("Failed to inspect token access for %s:%s", acl, action_name)
        return {
            "error": "AccessUnknown",
            "acl": acl,
            "action": action_name,
            "message": str(exc),
        }
    grant = grants.get(acl, {}).get(action_name)
    missing = [
        space
        for space in unique
        if grant is None or (not grant.all_spaces and space not in grant.spaces)
    ]
    return {
        "acl": acl,
        "action": action_name,
        "allowed": not missing,
        "missingSpaces": missing,
    }


def load_grants(client: CogniteClient) -> dict[str, dict[str, Grant]]:
    """ACL name → action → grant, limited to this client's project."""
    project = _project(client)
    inspection = client.iam.token.inspect()
    capabilities = _capability_items(inspection)

    grants: dict[str, dict[str, Grant]] = {}
    for capability in capabilities:
        dumped = _dump_capability(capability)
        if not _in_project(dumped, project):
            continue
        parsed = _acl_entry(dumped)
        if parsed is None:
            continue
        acl_name, entry = parsed
        scope = entry.get("scope")
        all_spaces, space_ids, other_scope = _parse_scope(scope)
        actions = entry.get("actions") or []
        if not isinstance(actions, list):
            continue
        by_action = grants.setdefault(acl_name, {})
        for raw_action in actions:
            action_name = str(raw_action).upper()
            by_action[action_name] = _merge(
                by_action.get(action_name),
                all_spaces,
                space_ids,
                other_scope,
            )
    return grants


def _capability_items(inspection: Any) -> list[Any]:
    """SDK returns a ``ProjectCapabilityList`` (a ``UserList``), not a builtin list."""
    capabilities = getattr(inspection, "capabilities", None)
    if capabilities is None and isinstance(inspection, dict):
        capabilities = inspection.get("capabilities")
    if isinstance(capabilities, (str, bytes)) or not isinstance(capabilities, Sequence):
        raise TypeError("Token inspection did not include a capability list")
    return list(capabilities)


def _project(client: CogniteClient) -> str:
    project = getattr(getattr(client, "config", None), "project", None)
    if not project or not str(project).strip():
        raise ValueError("CDF client has no project")
    return str(project)


def _dump_capability(capability: Any) -> dict[str, Any]:
    if isinstance(capability, dict):
        return capability
    dump = getattr(capability, "dump", None)
    if not callable(dump):
        raise TypeError("Token capability could not be serialized")
    dumped = dump(camel_case=True)
    if not isinstance(dumped, dict):
        raise TypeError("Token capability dump was not an object")
    return dumped


def _in_project(capability: dict[str, Any], project: str) -> bool:
    scope = capability.get("projectScope")
    if not isinstance(scope, dict):
        return True
    projects = scope.get("projects")
    if not isinstance(projects, list) or not projects:
        return True
    return project in projects


def _acl_entry(capability: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    for key, value in capability.items():
        if key == "projectScope" or not isinstance(value, dict):
            continue
        if "actions" in value:
            return key, value
    return None


def _parse_scope(scope: Any) -> tuple[bool, set[str], dict[str, Any] | None]:
    """Split a capability scope into space coverage and any other scope."""
    if not isinstance(scope, dict) or not scope:
        return False, set(), None
    if set(scope) == {"all"}:
        return True, set(), None
    if set(scope) == {"spaceIdScope"} and isinstance(scope.get("spaceIdScope"), dict):
        raw_ids = scope["spaceIdScope"].get("spaceIds") or []
        if isinstance(raw_ids, list):
            return False, {str(space_id) for space_id in raw_ids}, None
    return False, set(), scope


def _merge(
    current: Grant | None,
    all_spaces: bool,
    spaces: set[str],
    other_scope: dict[str, Any] | None,
) -> Grant:
    if current is not None and current.all_spaces:
        return current
    if all_spaces:
        return Grant(all_spaces=True, spaces=frozenset())
    merged = set(current.spaces) if current is not None else set()
    merged.update(spaces)
    others = list(current.other_scopes) if current is not None else []
    if other_scope is not None and other_scope not in others:
        others.append(other_scope)
    return Grant(all_spaces=False, spaces=frozenset(merged), other_scopes=tuple(others))


def _booleans_for_space(
    by_action: dict[str, Grant],
    space: str,
    action: str | None,
    *,
    include_common: bool,
) -> dict[str, bool]:
    names = _action_names(by_action, action, include_common=include_common)
    return {name: _covers(by_action.get(name), space) for name in names}


def _lists_for_acl(
    by_action: dict[str, Grant],
    action: str | None,
    *,
    include_common: bool,
) -> dict[str, dict[str, Any]]:
    names = _action_names(by_action, action, include_common=include_common)
    listed: dict[str, dict[str, Any]] = {}
    for name in names:
        grant = by_action.get(name)
        if grant is None:
            listed[name] = {"all": False, "spaces": []}
        elif grant.all_spaces:
            listed[name] = {"all": True, "spaces": []}
        else:
            item: dict[str, Any] = {"all": False, "spaces": sorted(grant.spaces)}
            if grant.other_scopes:
                item["scope"] = list(grant.other_scopes)
            listed[name] = item
    return listed


def _action_names(
    by_action: dict[str, Grant],
    action: str | None,
    *,
    include_common: bool,
) -> tuple[str, ...]:
    if action:
        return (action,)
    if include_common:
        return (*COMMON_ACTIONS, *_extra_actions(by_action))
    return tuple(sorted(by_action))


def _extra_actions(by_action: dict[str, Grant]) -> tuple[str, ...]:
    return tuple(sorted(name for name in by_action if name not in COMMON_ACTIONS))


def _covers(grant: Grant | None, space: str) -> bool:
    if grant is None:
        return False
    return grant.all_spaces or space in grant.spaces
