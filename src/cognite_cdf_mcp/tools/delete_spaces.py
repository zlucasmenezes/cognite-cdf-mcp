"""Tool: delete CDF spaces with dry-run."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.params import DEFAULT_DRY_RUN

logger = logging.getLogger(__name__)


def _serialize_space(space: Any) -> dict[str, Any]:
    return {
        "space": getattr(space, "space", None),
        "name": getattr(space, "name", None),
        "description": getattr(space, "description", None),
        "isGlobal": getattr(space, "is_global", None),
        "createdTime": getattr(space, "created_time", None),
        "lastUpdatedTime": getattr(space, "last_updated_time", None),
    }


def _parse_space_ids(spaces: list[str | dict[str, Any]] | str) -> list[str]:
    """Accept ``["sp_a"]``, ``[{"space": "sp_a"}]``, or a JSON string."""
    if isinstance(spaces, str):
        stripped = spaces.strip()
        if not stripped:
            return []
        # Single space id string (not JSON).
        if not stripped.startswith("["):
            return [stripped]
        parsed = json.loads(stripped)
        if not isinstance(parsed, list):
            raise TypeError("spaces must be a JSON array or a space id string")
        items: list[Any] = parsed
    else:
        items = list(spaces)

    ids: list[str] = []
    for item in items:
        if isinstance(item, str):
            space = item.strip()
            if not space:
                raise ValueError("space id must be non-empty")
            ids.append(space)
        elif isinstance(item, dict):
            space = item.get("space")
            if not space or not str(space).strip():
                raise ValueError("each space item requires space")
            ids.append(str(space).strip())
        else:
            raise TypeError("each space must be a string id or {space: ...}")
    return ids


def delete_spaces(
    client: CogniteClient,
    *,
    spaces: list[str | dict[str, Any]] | str,
    dry_run: bool = DEFAULT_DRY_RUN,
) -> str:
    """Delete one or more spaces by id.

    ``spaces`` example: ``["sp_x"]`` or ``[{"space": "sp_x"}]``.
    Defaults to ``DEFAULT_DRY_RUN`` (retrieve/report only). Pass ``dry_run=false``
    to delete. Requires ``dataModelsAcl:WRITE`` for an actual delete.
    """
    try:
        space_ids = _parse_space_ids(spaces)
        if not space_ids:
            raise ValueError("provide at least one space")

        if dry_run:
            existing = client.data_modeling.spaces.retrieve(spaces=space_ids)
            if existing is None:
                existing_list: list[Any] = []
            elif hasattr(existing, "space") and not hasattr(existing, "__iter__"):
                existing_list = [existing]
            else:
                existing_list = list(existing)
            found = {getattr(s, "space", None) for s in existing_list}
            missing = [s for s in space_ids if s not in found]
            return json.dumps(
                {
                    "dryRun": True,
                    "wouldDelete": bool(existing_list),
                    "requested": space_ids,
                    "existing": [_serialize_space(s) for s in existing_list],
                    "missing": missing,
                    "message": (
                        "Dry run only — spaces were not deleted. "
                        "Dependency conflicts are not validated in dry run."
                    ),
                },
                indent=2,
            )

        deleted = client.data_modeling.spaces.delete(spaces=space_ids)
        if deleted is None:
            deleted_list: list[Any] = []
        elif isinstance(deleted, str):
            deleted_list = [deleted]
        elif hasattr(deleted, "space") and not hasattr(deleted, "__iter__"):
            deleted_list = [deleted.space]
        else:
            deleted_list = [
                getattr(item, "space", item) if not isinstance(item, str) else item
                for item in deleted
            ]
        return json.dumps(
            {
                "dryRun": False,
                "deleted": bool(deleted_list),
                "count": len(deleted_list),
                "items": [{"space": s} for s in deleted_list],
            },
            indent=2,
        )
    except (TypeError, ValueError, json.JSONDecodeError, KeyError) as exc:
        return json.dumps({"error": "InvalidArgument", "message": str(exc)})
    except CogniteAPIError as exc:
        logger.exception("CDF API error deleting spaces")
        return json.dumps(
            {
                "error": "CogniteAPIError",
                "code": getattr(exc, "code", None),
                "message": str(exc),
            }
        )
    except CogniteException as exc:
        logger.exception("Cognite error deleting spaces")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error deleting spaces")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
