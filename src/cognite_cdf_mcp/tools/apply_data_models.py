"""Tool: create/update CDF data models with dry-run."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import DataModelApply, DataModelId
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


def _normalize_view_refs(item: dict[str, Any]) -> dict[str, Any]:
    """Force identity-only view entries to ``type: view`` so load keeps ViewId refs.

    Without ``type``, ``DataModelApply.load`` treats bare refs as empty
    ``ViewApply`` payloads, which would try to create empty views on apply.
    """
    views = item.get("views")
    if not isinstance(views, list):
        return item
    normalized: list[Any] = []
    changed = False
    for view in views:
        if not isinstance(view, dict):
            normalized.append(view)
            continue
        has_body = any(
            key in view
            for key in (
                "properties",
                "implements",
                "filter",
                "streamId",
                "stream_id",
            )
        )
        if has_body or view.get("type") == "view":
            normalized.append(view)
            continue
        space = view.get("space")
        external_id = view.get("externalId") or view.get("external_id")
        version = view.get("version")
        if not space or not external_id or not version:
            raise ValueError("each data model view ref requires space, externalId, and version")
        normalized.append(
            {
                "type": "view",
                "space": space,
                "externalId": external_id,
                "version": version,
            }
        )
        changed = True
    if not changed:
        return item
    out = dict(item)
    out["views"] = normalized
    return out


def _parse_data_model(item: dict[str, Any]) -> DataModelApply:
    try:
        return DataModelApply.load(_normalize_view_refs(item))
    except (TypeError, ValueError, KeyError) as exc:
        raise ValueError(f"invalid data model: {exc}") from exc


def _data_model_ref(item: DataModelApply) -> dict[str, str]:
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


def apply_data_models(
    client: CogniteClient,
    *,
    data_models: list[dict[str, Any]] | str,
    dry_run: bool = DEFAULT_DRY_RUN,
) -> str:
    """Create or update data models (upsert).

    Data model item example::
      {
        "space": "sp_x",
        "externalId": "Plant",
        "version": "v1",
        "views": [
          {"space": "sp_x", "externalId": "Asset", "version": "v1"}
        ]
      }

    Bare view refs (space / externalId / version only) stay as view references.
    Inline view definitions with ``properties`` are also accepted by the SDK.
    Defaults to ``DEFAULT_DRY_RUN`` (retrieve existing; no write). Pass
    ``dry_run=false`` to apply. Requires ``dataModelsAcl:WRITE`` for an actual write.

    Apply and retrieve-by-ids send at most ``MAX_SCHEMA_PER_REQUEST`` (100)
    data models per CDF call. If a later batch fails, the error includes
    ``completedBatches`` and the data model ids already applied.
    """
    space_ids: list[str] = []
    try:
        raw = require_object_list(parse_object_list(data_models), label="data model")
        applies = [_parse_data_model(item) for item in raw]
        space_ids = [item.space for item in applies]
        batches = schema_batches(applies)

        if dry_run:
            existing_list: list[Any] = []
            for batch in batches:
                existing = client.data_modeling.data_models.retrieve(
                    ids=[DataModelId(item.space, item.external_id, item.version) for item in batch],
                    inline_views=False,
                )
                existing_list.extend(as_list(existing))
            access = check_spaces(client, acl=MODELS_ACL, action="WRITE", spaces=space_ids)
            denied = is_denied(access)
            message = "Dry run only — data models were not written."
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
                result = client.data_modeling.data_models.apply(batch)
            except CogniteException as exc:
                return partial_cognite_error(
                    exc,
                    completed_batches=completed_batches,
                    items=succeeded,
                    action="applying data models",
                )
            completed_batches += 1
            succeeded.extend(_data_model_ref(item) for item in batch)
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
        logger.exception("CDF API error applying data models")
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
        logger.exception("Cognite error applying data models")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error applying data models")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
