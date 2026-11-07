"""Tool: create/update CDF spaces with dry-run."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import SpaceApply
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.access import MODELS_ACL, check_spaces, denial_detail, is_denied
from cognite_cdf_mcp.tools.params import (
    DEFAULT_DRY_RUN,
    MAX_SPACES_PER_REQUEST,
    parse_object_list,
)

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


def _as_list(result: Any) -> list[Any]:
    if result is None:
        return []
    if hasattr(result, "space") and not hasattr(result, "__iter__"):
        return [result]
    return list(result)


def _partial_cognite_error(
    exc: CogniteException,
    *,
    completed_batches: int,
    space_ids: list[str],
) -> str:
    if isinstance(exc, CogniteAPIError):
        logger.exception("CDF API error applying spaces")
        body: dict[str, Any] = {
            "error": "CogniteAPIError",
            "code": getattr(exc, "code", None),
            "message": str(exc),
        }
    else:
        logger.exception("Cognite error applying spaces")
        body = {"error": type(exc).__name__, "message": str(exc)}
    if completed_batches:
        body["completedBatches"] = completed_batches
        body["items"] = [{"space": space_id} for space_id in space_ids]
    return json.dumps(body)


def _parse_space(item: dict[str, Any]) -> SpaceApply:
    space = item.get("space")
    if not space or not str(space).strip():
        raise ValueError("each space item requires space")
    return SpaceApply(
        space=str(space).strip(),
        name=item.get("name"),
        description=item.get("description"),
    )


def _access_on_forbidden(
    client: CogniteClient,
    exc: CogniteException,
    spaces: list[str],
) -> dict[str, Any] | None:
    if not isinstance(exc, CogniteAPIError) or getattr(exc, "code", None) != 403:
        return None
    return check_spaces(client, acl=MODELS_ACL, action="WRITE", spaces=spaces)


def apply_spaces(
    client: CogniteClient,
    *,
    spaces: list[dict[str, Any]] | str,
    dry_run: bool = DEFAULT_DRY_RUN,
) -> str:
    """Create or update spaces (upsert).

    Space item example::
      {
        "space": "sp_x",
        "name": "Sandbox X",
        "description": "Temporary sandbox"
      }

    Defaults to ``DEFAULT_DRY_RUN`` (validates / retrieves existing; no write).
    Pass ``dry_run=false`` to apply. Requires ``dataModelsAcl:WRITE`` for an
    actual write.

    Apply and retrieve-by-ids send at most ``MAX_SPACES_PER_REQUEST`` (100)
    spaces per CDF call. If a later batch fails, the error includes
    ``completedBatches`` and the space ids already applied.
    """
    space_ids: list[str] = []
    try:
        items = parse_object_list(spaces)
        if not items:
            raise ValueError("provide at least one space")
        for item in items:
            if not isinstance(item, dict):
                raise TypeError("each space item must be an object")

        applies = [_parse_space(item) for item in items]
        space_ids = [item.space for item in applies]

        if dry_run:
            existing_list: list[Any] = []
            for batch in _chunks(applies):
                existing = client.data_modeling.spaces.retrieve(
                    spaces=[item.space for item in batch]
                )
                existing_list.extend(_as_list(existing))
            access = check_spaces(client, acl=MODELS_ACL, action="WRITE", spaces=space_ids)
            denied = is_denied(access)
            message = "Dry run only — spaces were not written."
            if denied:
                message = f"{message} {denial_detail(access)}"
            return json.dumps(
                {
                    "dryRun": True,
                    "wouldApply": not denied,
                    "requested": len(applies),
                    "alreadyExist": len(existing_list),
                    "access": access,
                    "payload": [a.dump(camel_case=True) for a in applies],
                    "existing": [_serialize_space(s) for s in existing_list],
                    "message": message,
                },
                indent=2,
            )

        applied: list[Any] = []
        succeeded: list[str] = []
        completed_batches = 0
        for batch in _chunks(applies):
            try:
                result = client.data_modeling.spaces.apply(batch)
            except CogniteException as exc:
                return _partial_cognite_error(
                    exc,
                    completed_batches=completed_batches,
                    space_ids=succeeded,
                )
            completed_batches += 1
            succeeded.extend(item.space for item in batch)
            applied.extend(_as_list(result))
        return json.dumps(
            {
                "dryRun": False,
                "applied": True,
                "count": len(applied),
                "items": [_serialize_space(s) for s in applied],
            },
            indent=2,
        )
    except (TypeError, ValueError, json.JSONDecodeError, KeyError) as exc:
        return json.dumps({"error": "InvalidArgument", "message": str(exc)})
    except CogniteAPIError as exc:
        logger.exception("CDF API error applying spaces")
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
        logger.exception("Cognite error applying spaces")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error applying spaces")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
