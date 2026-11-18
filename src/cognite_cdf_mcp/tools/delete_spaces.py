"""Tool: delete CDF spaces with dry-run."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.access import MODELS_ACL, check_spaces, denial_detail, is_denied
from cognite_cdf_mcp.tools.params import DEFAULT_DRY_RUN, MAX_SPACES_PER_REQUEST

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


def _chunks(items: list[Any], size: int = MAX_SPACES_PER_REQUEST) -> list[list[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _as_space_list(result: Any) -> list[Any]:
    if result is None:
        return []
    if hasattr(result, "space") and not hasattr(result, "__iter__"):
        return [result]
    return list(result)


def _deleted_space_ids(deleted: Any) -> list[Any]:
    if deleted is None:
        return []
    if isinstance(deleted, str):
        return [deleted]
    if hasattr(deleted, "space") and not hasattr(deleted, "__iter__"):
        return [deleted.space]
    return [getattr(item, "space", item) if not isinstance(item, str) else item for item in deleted]


def _partial_cognite_error(
    exc: CogniteException,
    *,
    completed_batches: int,
    space_ids: list[str],
    access: dict[str, Any] | None = None,
) -> str:
    if isinstance(exc, CogniteAPIError):
        logger.exception("CDF API error deleting spaces")
        body: dict[str, Any] = {
            "error": "CogniteAPIError",
            "code": getattr(exc, "code", None),
            "message": str(exc),
        }
    else:
        logger.exception("Cognite error deleting spaces")
        body = {"error": type(exc).__name__, "message": str(exc)}
    if completed_batches:
        body["completedBatches"] = completed_batches
        body["items"] = [{"space": space_id} for space_id in space_ids]
    if access is not None:
        body["access"] = access
    return json.dumps(body)


def _access_on_forbidden(
    client: CogniteClient,
    exc: CogniteException,
    spaces: list[str],
) -> dict[str, Any] | None:
    if not isinstance(exc, CogniteAPIError) or getattr(exc, "code", None) != 403:
        return None
    return check_spaces(client, acl=MODELS_ACL, action="WRITE", spaces=spaces)


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

    Delete and retrieve-by-ids send at most ``MAX_SPACES_PER_REQUEST`` (100)
    spaces per CDF call. Real deletes retrieve first and only send ids that
    exist; missing ids are reported in ``missing`` (or ``NotFound`` when none
    exist). If a later batch fails, the error includes ``completedBatches`` and
    the space ids already deleted. Dry run does not validate dependency
    conflicts.
    """
    space_ids: list[str] = []
    try:
        space_ids = _parse_space_ids(spaces)
        if not space_ids:
            raise ValueError("provide at least one space")

        if dry_run:
            existing_list: list[Any] = []
            for batch in _chunks(space_ids):
                existing = client.data_modeling.spaces.retrieve(spaces=batch)
                existing_list.extend(_as_space_list(existing))
            found = {getattr(s, "space", None) for s in existing_list}
            missing = [s for s in space_ids if s not in found]
            access = check_spaces(client, acl=MODELS_ACL, action="WRITE", spaces=space_ids)
            denied = is_denied(access)
            message = (
                "Dry run only — spaces were not deleted. "
                "Dependency conflicts are not validated in dry run."
            )
            if denied:
                message = f"{message} {denial_detail(access)}"
            return json.dumps(
                {
                    "dryRun": True,
                    "wouldDelete": bool(existing_list) and not denied,
                    "requested": space_ids,
                    "existing": [_serialize_space(s) for s in existing_list],
                    "missing": missing,
                    "access": access,
                    "message": message,
                },
                indent=2,
            )

        existing_list: list[Any] = []
        for batch in _chunks(space_ids):
            existing_list.extend(_as_space_list(client.data_modeling.spaces.retrieve(spaces=batch)))
        found = {getattr(s, "space", None) for s in existing_list}
        missing = [s for s in space_ids if s not in found]
        to_delete = [s for s in space_ids if s in found]
        if not to_delete:
            return json.dumps(
                {
                    "error": "NotFound",
                    "message": "none of the requested spaces exist",
                    "missing": missing,
                }
            )

        deleted_list: list[Any] = []
        succeeded: list[str] = []
        completed_batches = 0
        for batch in _chunks(to_delete):
            try:
                deleted = client.data_modeling.spaces.delete(spaces=batch)
            except CogniteException as exc:
                return _partial_cognite_error(
                    exc,
                    completed_batches=completed_batches,
                    space_ids=succeeded,
                    access=_access_on_forbidden(client, exc, space_ids),
                )
            completed_batches += 1
            succeeded.extend(batch)
            deleted_list.extend(_deleted_space_ids(deleted))
        body: dict[str, Any] = {
            "dryRun": False,
            "deleted": bool(deleted_list),
            "count": len(deleted_list),
            "items": [{"space": s} for s in deleted_list],
        }
        if missing:
            body["missing"] = missing
        return json.dumps(body, indent=2)
    except (TypeError, ValueError, json.JSONDecodeError, KeyError) as exc:
        return json.dumps({"error": "InvalidArgument", "message": str(exc)})
    except CogniteAPIError as exc:
        logger.exception("CDF API error deleting spaces")
        body = {
            "error": "CogniteAPIError",
            "code": getattr(exc, "code", None),
            "message": str(exc),
        }
        access = _access_on_forbidden(client, exc, space_ids)
        if access is not None:
            body["access"] = access
        return json.dumps(body)
    except CogniteException as exc:
        logger.exception("Cognite error deleting spaces")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error deleting spaces")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
