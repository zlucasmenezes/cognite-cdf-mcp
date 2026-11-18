"""Tool: create/update CDF views with dry-run."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import RecordViewApply, ViewApply, ViewId
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.access import MODELS_ACL, check_spaces, denial_detail, is_denied
from cognite_cdf_mcp.tools.params import DEFAULT_DRY_RUN, MAX_SCHEMA_PER_REQUEST, parse_object_list
from cognite_cdf_mcp.tools.schema_common import (
    as_list,
    dump_schema,
    partial_cognite_error,
    require_object_list,
    schema_batches,
)

logger = logging.getLogger(__name__)


def _parse_view(item: dict[str, Any]) -> ViewApply | RecordViewApply:
    """Load a view apply; record-backed views use ``streamId``."""
    try:
        if item.get("streamId") is not None or item.get("stream_id") is not None:
            return RecordViewApply.load(item)
        return ViewApply.load(item)
    except (TypeError, ValueError, KeyError) as exc:
        raise ValueError(f"invalid view: {exc}") from exc


def _view_ref(item: ViewApply | RecordViewApply) -> dict[str, str]:
    return {
        "space": item.space,
        "externalId": item.external_id,
        "version": item.version,
    }


def _access_on_forbidden(
    client: CogniteClient,
    exc: CogniteException,
    spaces: list[str],
) -> dict[str, Any] | None:
    if not isinstance(exc, CogniteAPIError) or getattr(exc, "code", None) != 403:
        return None
    return check_spaces(client, acl=MODELS_ACL, action="WRITE", spaces=spaces)


def apply_views(
    client: CogniteClient,
    *,
    views: list[dict[str, Any]] | str,
    dry_run: bool = DEFAULT_DRY_RUN,
) -> str:
    """Create or update views (upsert).

    View item example::
      {
        "space": "sp_x",
        "externalId": "Asset",
        "version": "v1",
        "properties": {
          "name": {
            "container": {"space": "sp_x", "externalId": "Asset"},
            "containerPropertyIdentifier": "name"
          }
        }
      }

    Record-backed views include ``streamId`` and load as ``RecordViewApply``.
    Defaults to ``DEFAULT_DRY_RUN`` (retrieve existing; no write). Pass
    ``dry_run=false`` to apply. Requires ``dataModelsAcl:WRITE`` for an actual write.

    Apply and retrieve-by-ids send at most ``MAX_SCHEMA_PER_REQUEST`` (100)
    views per CDF call. If a later batch fails, the error includes
    ``completedBatches`` and the view ids already applied.
    """
    space_ids: list[str] = []
    try:
        raw = require_object_list(parse_object_list(views), label="view")
        applies = [_parse_view(item) for item in raw]
        space_ids = [item.space for item in applies]
        batches = schema_batches(applies)

        if dry_run:
            existing_list: list[Any] = []
            for batch in batches:
                existing = client.data_modeling.views.retrieve(
                    ids=[ViewId(item.space, item.external_id, item.version) for item in batch],
                    include_inherited_properties=False,
                    all_versions=False,
                )
                existing_list.extend(as_list(existing))
            access = check_spaces(client, acl=MODELS_ACL, action="WRITE", spaces=space_ids)
            denied = is_denied(access)
            message = "Dry run only — views were not written."
            if denied:
                message = f"{message} {denial_detail(access)}"
            return json.dumps(
                {
                    "dryRun": True,
                    "wouldApply": not denied,
                    "requested": len(applies),
                    "alreadyExist": len(existing_list),
                    "batches": len(batches),
                    "maxBatchSize": MAX_SCHEMA_PER_REQUEST,
                    "access": access,
                    "payload": [dump_schema(item) for item in applies],
                    "existing": [dump_schema(item) for item in existing_list],
                    "message": message,
                },
                indent=2,
            )

        applied: list[Any] = []
        succeeded: list[dict[str, str]] = []
        completed_batches = 0
        for batch in batches:
            try:
                result = client.data_modeling.views.apply(batch)
            except CogniteException as exc:
                return partial_cognite_error(
                    exc,
                    completed_batches=completed_batches,
                    items=succeeded,
                    action="applying views",
                    access=_access_on_forbidden(client, exc, space_ids),
                )
            completed_batches += 1
            succeeded.extend(_view_ref(item) for item in batch)
            applied.extend(as_list(result))
        return json.dumps(
            {
                "dryRun": False,
                "applied": True,
                "count": len(applied),
                "batches": len(batches),
                "maxBatchSize": MAX_SCHEMA_PER_REQUEST,
                "items": [dump_schema(item) for item in applied],
            },
            indent=2,
        )
    except (TypeError, ValueError, json.JSONDecodeError, KeyError) as exc:
        return json.dumps({"error": "InvalidArgument", "message": str(exc)})
    except CogniteAPIError as exc:
        logger.exception("CDF API error applying views")
        body: dict[str, Any] = {
            "error": "CogniteAPIError",
            "code": getattr(exc, "code", None),
            "message": str(exc),
        }
        access = _access_on_forbidden(client, exc, space_ids)
        if access is not None:
            body["access"] = access
        return json.dumps(body)
    except CogniteException as exc:
        logger.exception("Cognite error applying views")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error applying views")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
