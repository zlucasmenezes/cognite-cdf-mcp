"""Actionable NotFound / context helpers for tool responses."""

from __future__ import annotations

import logging
from typing import Any, Literal

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import ViewId
from cognite.client.exceptions import CogniteAPIError, CogniteException

logger = logging.getLogger(__name__)

InstanceType = Literal["node", "edge"]


def _space_exists(client: CogniteClient, space: str) -> bool | None:
    """Return True/False if known; None if the check itself failed."""
    try:
        result = client.data_modeling.spaces.retrieve(spaces=space)
        if result is None:
            return False
        if hasattr(result, "space"):
            return True
        return bool(list(result))
    except (CogniteAPIError, CogniteException):
        logger.exception("Failed checking whether space exists: %s", space)
        return None


def _view_exists(client: CogniteClient, space: str, external_id: str, version: str) -> bool | None:
    try:
        views = client.data_modeling.views.retrieve(
            ids=ViewId(space=space, external_id=external_id, version=version),
            include_inherited_properties=False,
        )
        return bool(views)
    except (CogniteAPIError, CogniteException):
        logger.exception("Failed checking whether view exists")
        return None


def not_found_space(client: CogniteClient, space: str) -> dict[str, Any]:
    return {
        "error": "NotFound",
        "message": (
            f"Space not found: space={space!r}. "
            "Call list_spaces (with cursor if needed) to discover valid space ids."
        ),
        "hints": [
            "Use list_spaces to browse available spaces.",
            "Space ids are case-sensitive.",
        ],
    }


def not_found_view(
    client: CogniteClient,
    *,
    space: str,
    external_id: str,
    version: str,
) -> dict[str, Any]:
    space_ok = _space_exists(client, space)
    hints: list[str] = [
        "View ids are case-sensitive; version must match exactly (e.g. v1 / v1.0.0).",
        "Call list_views with the space filter to see available externalId/version pairs.",
    ]
    if space_ok is False:
        message = (
            f"View not found: space={space!r}, externalId={external_id!r}, version={version!r}. "
            f"Space {space!r} does not exist."
        )
        hints.insert(0, "Create or pick an existing space before retrieving the view.")
    elif space_ok is True:
        message = (
            f"View not found: space={space!r}, externalId={external_id!r}, version={version!r}. "
            f"Space {space!r} exists — check externalId/version via list_views."
        )
    else:
        message = (
            f"View not found: space={space!r}, externalId={external_id!r}, version={version!r}."
        )
    return {"error": "NotFound", "message": message, "hints": hints}


def not_found_data_model(
    client: CogniteClient,
    *,
    space: str,
    external_id: str,
    version: str,
) -> dict[str, Any]:
    space_ok = _space_exists(client, space)
    hints = [
        "Call list_data_models with the space filter to see externalId/version pairs.",
        "Versions are exact strings (e.g. v1).",
    ]
    if space_ok is False:
        message = (
            f"Data model not found: space={space!r}, externalId={external_id!r}, "
            f"version={version!r}. Space {space!r} does not exist."
        )
    elif space_ok is True:
        message = (
            f"Data model not found: space={space!r}, externalId={external_id!r}, "
            f"version={version!r}. Space {space!r} exists — verify externalId/version."
        )
    else:
        message = (
            f"Data model not found: space={space!r}, externalId={external_id!r}, "
            f"version={version!r}."
        )
    return {"error": "NotFound", "message": message, "hints": hints}


def not_found_container(
    client: CogniteClient,
    *,
    space: str,
    external_id: str,
) -> dict[str, Any]:
    space_ok = _space_exists(client, space)
    hints = [
        "Call list_containers with the space filter to discover container externalIds.",
    ]
    if space_ok is False:
        message = (
            f"Container not found: space={space!r}, externalId={external_id!r}. "
            f"Space {space!r} does not exist."
        )
    elif space_ok is True:
        message = (
            f"Container not found: space={space!r}, externalId={external_id!r}. "
            f"Space {space!r} exists — verify the container externalId."
        )
    else:
        message = f"Container not found: space={space!r}, externalId={external_id!r}."
    return {"error": "NotFound", "message": message, "hints": hints}


def not_found_instance(
    client: CogniteClient,
    *,
    space: str,
    external_id: str,
    instance_type: InstanceType,
    view_space: str | None = None,
    view_external_id: str | None = None,
    view_version: str | None = None,
) -> dict[str, Any]:
    space_ok = _space_exists(client, space)
    hints: list[str] = [
        "Try search_instances or query_instances on the expected view.",
        "If you projected through a view, the node may exist without properties for that view "
        "(view filter / wrong version) — call inspect_instance to see involved views/containers.",
    ]

    view_parts = (view_space, view_external_id, view_version)
    if any(view_parts) and all(view_parts):
        view_ok = _view_exists(client, view_space, view_external_id, view_version)  # type: ignore[arg-type]
        if view_ok is False:
            hints.insert(
                0,
                (
                    f"Requested view {view_space}/{view_external_id}/{view_version} was not found; "
                    "retrieve without view_* or fix the view reference."
                ),
            )

    if space_ok is False:
        message = (
            f"Instance not found: type={instance_type!r}, space={space!r}, "
            f"externalId={external_id!r}. Space {space!r} does not exist."
        )
        hints.insert(0, "Pick an existing instance space (list_spaces / get_space).")
    elif space_ok is True:
        message = (
            f"Instance not found: type={instance_type!r}, space={space!r}, "
            f"externalId={external_id!r}. Space {space!r} exists — the id may be wrong, "
            "or a view projection/filter hid the instance."
        )
    else:
        message = (
            f"Instance not found: type={instance_type!r}, space={space!r}, "
            f"externalId={external_id!r}."
        )

    return {
        "error": "NotFound",
        "message": message,
        "hints": hints,
        "context": {
            "space": space,
            "spaceExists": space_ok,
            "instanceType": instance_type,
            "externalId": external_id,
        },
    }
