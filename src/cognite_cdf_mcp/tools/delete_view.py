"""Tool: delete a specific CDF view."""

from __future__ import annotations

import json
import logging

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import ViewId
from cognite.client.exceptions import CogniteAPIError, CogniteException

logger = logging.getLogger(__name__)


def _view_id_payload(space: str, external_id: str, version: str) -> dict[str, str]:
    return {
        "space": space,
        "externalId": external_id,
        "version": version,
    }


def delete_view(
    client: CogniteClient,
    *,
    space: str,
    external_id: str,
    version: str,
    dry_run: bool = False,
) -> str:
    """Delete one view by space, externalId, and version.

    When ``dry_run`` is True, only checks whether the view exists and reports
    what would be deleted — no write is performed.
    """
    view_id = ViewId(space=space, external_id=external_id, version=version)
    try:
        if dry_run:
            existing = client.data_modeling.views.retrieve(
                ids=view_id,
                include_inherited_properties=False,
            )
            if not existing:
                return json.dumps(
                    {
                        "dryRun": True,
                        "wouldDelete": False,
                        "message": (
                            f"View not found: space={space!r}, "
                            f"externalId={external_id!r}, version={version!r}"
                        ),
                    },
                    indent=2,
                )
            view = existing[0]
            return json.dumps(
                {
                    "dryRun": True,
                    "wouldDelete": True,
                    "item": {
                        **_view_id_payload(view.space, view.external_id, view.version),
                        "name": view.name,
                        "description": view.description,
                    },
                    "message": (
                        "Dry run only — view was not deleted. "
                        "Dependency conflicts are not validated in dry run."
                    ),
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
        return json.dumps(
            {
                "error": "CogniteAPIError",
                "code": getattr(exc, "code", None),
                "message": str(exc),
            }
        )
    except CogniteException as exc:
        logger.exception("Cognite error deleting view")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error deleting view")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
