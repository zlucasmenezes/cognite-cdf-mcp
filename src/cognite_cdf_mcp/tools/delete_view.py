"""Tool: delete a specific CDF view."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import ViewId
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.access import MODELS_ACL, check_spaces, denial_detail, is_denied
from cognite_cdf_mcp.tools.params import DEFAULT_DRY_RUN

logger = logging.getLogger(__name__)


def _view_id_payload(space: str, external_id: str, version: str) -> dict[str, str]:
    return {
        "space": space,
        "externalId": external_id,
        "version": version,
    }


def _access_on_forbidden(
    client: CogniteClient,
    exc: CogniteException,
    space: str,
) -> dict[str, Any] | None:
    if not isinstance(exc, CogniteAPIError) or getattr(exc, "code", None) != 403:
        return None
    return check_spaces(client, acl=MODELS_ACL, action="WRITE", spaces=[space])


def delete_view(
    client: CogniteClient,
    *,
    space: str,
    external_id: str,
    version: str,
    dry_run: bool = DEFAULT_DRY_RUN,
) -> str:
    """Delete one view by space, externalId, and version.

    Defaults to ``DEFAULT_DRY_RUN`` (existence check / preview only). Pass
    ``dry_run=false`` to permanently delete the view version. Requires
    ``dataModelsAcl:WRITE`` for an actual delete. Dry run reports ``access`` and
    sets ``wouldDelete`` false when WRITE is missing.
    """
    view_id = ViewId(space=space, external_id=external_id, version=version)
    try:
        if dry_run:
            existing = client.data_modeling.views.retrieve(
                ids=view_id,
                include_inherited_properties=False,
            )
            access = check_spaces(client, acl=MODELS_ACL, action="WRITE", spaces=[space])
            denied = is_denied(access)
            if not existing:
                message = (
                    f"View not found: space={space!r}, "
                    f"externalId={external_id!r}, version={version!r}"
                )
                if denied:
                    message = f"{message} {denial_detail(access)}"
                return json.dumps(
                    {
                        "dryRun": True,
                        "wouldDelete": False,
                        "access": access,
                        "message": message,
                    },
                    indent=2,
                )
            view = existing[0]
            message = (
                "Dry run only — view was not deleted. "
                "Dependency conflicts are not validated in dry run."
            )
            if denied:
                message = f"{message} {denial_detail(access)}"
            return json.dumps(
                {
                    "dryRun": True,
                    "wouldDelete": not denied,
                    "access": access,
                    "item": {
                        **_view_id_payload(view.space, view.external_id, view.version),
                        "name": view.name,
                        "description": view.description,
                    },
                    "message": message,
                },
                indent=2,
            )

        deleted = client.data_modeling.views.delete(ids=view_id)
        if not deleted:
            return json.dumps(
                {
                    "dryRun": False,
                    "deleted": False,
                    "message": (
                        f"Nothing deleted for view: space={space!r}, "
                        f"externalId={external_id!r}, version={version!r}. "
                        "It may not exist."
                    ),
                },
                indent=2,
            )
        item = deleted[0]
        return json.dumps(
            {
                "dryRun": False,
                "deleted": True,
                "item": _view_id_payload(item.space, item.external_id, item.version),
            },
            indent=2,
        )
    except CogniteAPIError as exc:
        logger.exception("CDF API error deleting view")
        body: dict[str, Any] = {
            "error": "CogniteAPIError",
            "code": getattr(exc, "code", None),
            "message": str(exc),
        }
        access = _access_on_forbidden(client, exc, space)
        if access is not None:
            body["access"] = access
        return json.dumps(body)
    except CogniteException as exc:
        logger.exception("Cognite error deleting view")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error deleting view")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
