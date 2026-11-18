"""Tool: delete CDF data models with dry-run."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import DataModelId
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.access import MODELS_ACL, check_spaces, denial_detail, is_denied
from cognite_cdf_mcp.tools.params import DEFAULT_DRY_RUN, MAX_SCHEMA_PER_REQUEST, chunk
from cognite_cdf_mcp.tools.schema_common import as_list, dump_schema, partial_cognite_error

logger = logging.getLogger(__name__)


def _parse_data_model_ids(data_models: list[dict[str, Any]] | str) -> list[DataModelId]:
    """Accept ``[{"space": "sp", "externalId": "m", "version": "v1"}]`` or a JSON string."""
    if isinstance(data_models, str):
        stripped = data_models.strip()
        if not stripped:
            return []
        if not stripped.startswith("["):
            raise TypeError("data_models must be a JSON array of objects")
        parsed = json.loads(stripped)
        if not isinstance(parsed, list):
            raise TypeError("data_models must be a JSON array")
        items: list[Any] = parsed
    else:
        items = list(data_models)

    ids: list[DataModelId] = []
    for item in items:
        if not isinstance(item, dict):
            raise TypeError(
                "each data model item must be an object with space, externalId, and version"
            )
        space = item.get("space")
        external_id = item.get("externalId") or item.get("external_id")
        version = item.get("version")
        if not space or not str(space).strip():
            raise ValueError("each data model item requires space")
        if not external_id or not str(external_id).strip():
            raise ValueError("each data model item requires externalId")
        if not version or not str(version).strip():
            raise ValueError("each data model item requires version")
        ids.append(DataModelId(str(space).strip(), str(external_id).strip(), str(version).strip()))
    return ids


def _ref_dict(model_id: DataModelId) -> dict[str, str]:
    return {
        "space": model_id.space,
        "externalId": model_id.external_id,
        "version": model_id.version,
    }


def _access_on_forbidden(
    client: CogniteClient,
    exc: CogniteException,
    spaces: list[str],
) -> dict[str, Any] | None:
    if not isinstance(exc, CogniteAPIError) or getattr(exc, "code", None) != 403:
        return None
    return check_spaces(client, acl=MODELS_ACL, action="WRITE", spaces=spaces)


def delete_data_models(
    client: CogniteClient,
    *,
    data_models: list[dict[str, Any]] | str,
    dry_run: bool = DEFAULT_DRY_RUN,
) -> str:
    """Delete one or more data models by space/externalId/version.

    ``data_models`` example::
      [{"space": "sp_x", "externalId": "Plant", "version": "v1"}]

    Defaults to ``DEFAULT_DRY_RUN`` (retrieve/report only). Pass ``dry_run=false``
    to delete. Requires ``dataModelsAcl:WRITE`` for an actual delete.

    Delete and retrieve-by-ids send at most ``MAX_SCHEMA_PER_REQUEST`` (100)
    data models per CDF call. Real deletes retrieve first and only send ids that
    exist; missing ids are reported in ``missing`` (or ``NotFound`` when none
    exist). If a later batch fails, the error includes ``completedBatches`` and
    the data model ids already deleted. Dry run does not validate dependency
    conflicts. Deleting a data model does not delete its referenced views.
    """
    space_ids: list[str] = []
    try:
        ids = _parse_data_model_ids(data_models)
        if not ids:
            raise ValueError("provide at least one data model")
        space_ids = [item.space for item in ids]
        batches = chunk(ids, MAX_SCHEMA_PER_REQUEST)

        if dry_run:
            existing_list: list[Any] = []
            for batch in batches:
                existing = client.data_modeling.data_models.retrieve(
                    ids=batch,
                    inline_views=False,
                )
                existing_list.extend(as_list(existing))
            found = {
                (
                    getattr(item, "space", None),
                    getattr(item, "external_id", None),
                    getattr(item, "version", None),
                )
                for item in existing_list
            }
            missing = [
                _ref_dict(item)
                for item in ids
                if (item.space, item.external_id, item.version) not in found
            ]
            access = check_spaces(client, acl=MODELS_ACL, action="WRITE", spaces=space_ids)
            denied = is_denied(access)
            message = (
                "Dry run only — data models were not deleted. "
                "Referenced views are not deleted with the data model. "
                "Dependency conflicts are not validated in dry run."
            )
            if denied:
                message = f"{message} {denial_detail(access)}"
            return json.dumps(
                {
                    "dryRun": True,
                    "wouldDelete": bool(existing_list) and not denied,
                    "requested": len(ids),
                    "found": len(existing_list),
                    "missing": missing,
                    "batches": len(batches),
                    "maxBatchSize": MAX_SCHEMA_PER_REQUEST,
                    "access": access,
                    "items": [dump_schema(item) for item in existing_list],
                    "message": message,
                },
                indent=2,
            )

        existing_list: list[Any] = []
        for batch in batches:
            existing_list.extend(
                as_list(
                    client.data_modeling.data_models.retrieve(
                        ids=batch,
                        inline_views=False,
                    )
                )
            )
        found = {
            (
                getattr(item, "space", None),
                getattr(item, "external_id", None),
                getattr(item, "version", None),
            )
            for item in existing_list
        }
        missing = [
            _ref_dict(item)
            for item in ids
            if (item.space, item.external_id, item.version) not in found
        ]
        to_delete = [item for item in ids if (item.space, item.external_id, item.version) in found]
        if not to_delete:
            return json.dumps(
                {
                    "error": "NotFound",
                    "message": "none of the requested data models exist",
                    "missing": missing,
                }
            )

        delete_batches = chunk(to_delete, MAX_SCHEMA_PER_REQUEST)
        deleted_items: list[dict[str, str]] = []
        succeeded: list[dict[str, str]] = []
        completed_batches = 0
        for batch in delete_batches:
            try:
                deleted = client.data_modeling.data_models.delete(ids=batch)
            except CogniteException as exc:
                return partial_cognite_error(
                    exc,
                    completed_batches=completed_batches,
                    items=succeeded,
                    action="deleting data models",
                    access=_access_on_forbidden(client, exc, space_ids),
                )
            completed_batches += 1
            succeeded.extend(_ref_dict(item) for item in batch)
            for item in deleted or []:
                if isinstance(item, DataModelId):
                    deleted_items.append(_ref_dict(item))
                elif isinstance(item, tuple) and len(item) >= 3:
                    deleted_items.append(
                        {
                            "space": str(item[0]),
                            "externalId": str(item[1]),
                            "version": str(item[2]),
                        }
                    )
        body: dict[str, Any] = {
            "dryRun": False,
            "deleted": bool(deleted_items or succeeded),
            "count": len(deleted_items) if deleted_items else len(succeeded),
            "batches": len(delete_batches),
            "maxBatchSize": MAX_SCHEMA_PER_REQUEST,
            "items": deleted_items or succeeded,
        }
        if missing:
            body["missing"] = missing
        return json.dumps(body, indent=2)
    except (TypeError, ValueError, json.JSONDecodeError, KeyError) as exc:
        return json.dumps({"error": "InvalidArgument", "message": str(exc)})
    except CogniteAPIError as exc:
        logger.exception("CDF API error deleting data models")
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
        logger.exception("Cognite error deleting data models")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error deleting data models")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
