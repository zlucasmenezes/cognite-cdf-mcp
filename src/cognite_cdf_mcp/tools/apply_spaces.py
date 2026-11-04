"""Tool: create/update CDF spaces with dry-run."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import SpaceApply
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.params import DEFAULT_DRY_RUN, parse_object_list

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


def _parse_space(item: dict[str, Any]) -> SpaceApply:
    space = item.get("space")
    if not space or not str(space).strip():
        raise ValueError("each space item requires space")
    return SpaceApply(
        space=str(space).strip(),
        name=item.get("name"),
        description=item.get("description"),
    )


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
    """
    try:
        items = parse_object_list(spaces)
        if not items:
            raise ValueError("provide at least one space")
        for item in items:
            if not isinstance(item, dict):
                raise TypeError("each space item must be an object")

        applies = [_parse_space(item) for item in items]

        if dry_run:
            existing = client.data_modeling.spaces.retrieve(spaces=[a.space for a in applies])
            if existing is None:
                existing_list: list[Any] = []
            elif hasattr(existing, "space") and not hasattr(existing, "__iter__"):
                existing_list = [existing]
            else:
                existing_list = list(existing)
            return json.dumps(
                {
                    "dryRun": True,
                    "wouldApply": True,
                    "requested": len(applies),
                    "alreadyExist": len(existing_list),
                    "payload": [a.dump(camel_case=True) for a in applies],
                    "existing": [_serialize_space(s) for s in existing_list],
                    "message": "Dry run only — spaces were not written.",
                },
                indent=2,
            )

        result = client.data_modeling.spaces.apply(applies)
        if result is None:
            applied: list[Any] = []
        elif hasattr(result, "space") and not hasattr(result, "__iter__"):
            applied = [result]
        else:
            applied = list(result)
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
        return json.dumps(
            {
                "error": "CogniteAPIError",
                "code": getattr(exc, "code", None),
                "message": str(exc),
            }
        )
    except CogniteException as exc:
        logger.exception("Cognite error applying spaces")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error applying spaces")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
