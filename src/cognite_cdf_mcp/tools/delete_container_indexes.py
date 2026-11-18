"""Tool: delete indexes from CDF containers with dry-run."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import ContainerId
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.access import MODELS_ACL, check_spaces, denial_detail, is_denied
from cognite_cdf_mcp.tools.params import (
    DEFAULT_DRY_RUN,
    MAX_CONTAINER_INDEX_DELETE,
    chunk,
    parse_object_list,
)
from cognite_cdf_mcp.tools.schema_common import as_list, dump_schema, require_object_list

logger = logging.getLogger(__name__)

IndexRef = tuple[ContainerId, str]


def _parse_index_ref(item: dict[str, Any]) -> IndexRef:
    space = item.get("space")
    container_external_id = (
        item.get("containerExternalId")
        or item.get("container_external_id")
        or item.get("externalId")
        or item.get("external_id")
    )
    identifier = item.get("identifier") or item.get("index") or item.get("indexExternalId")
    if not space or not str(space).strip():
        raise ValueError("each index item requires space")
    if not container_external_id or not str(container_external_id).strip():
        raise ValueError(
            "each index item requires containerExternalId (or externalId of the container)"
        )
    if not identifier or not str(identifier).strip():
        raise ValueError("each index item requires identifier (index name)")
    return (
        ContainerId(str(space).strip(), str(container_external_id).strip()),
        str(identifier).strip(),
    )


def _ref_dict(ref: IndexRef) -> dict[str, str]:
    container_id, identifier = ref
    return {
        "space": container_id.space,
        "containerExternalId": container_id.external_id,
        "identifier": identifier,
    }


def _existing_index_names(container: Any) -> set[str]:
    indexes = getattr(container, "indexes", None) or {}
    if isinstance(indexes, dict):
        return {str(key) for key in indexes}
    return set()


def _partial_error(
    exc: CogniteException,
    *,
    completed_batches: int,
    items: list[dict[str, str]],
) -> str:
    if isinstance(exc, CogniteAPIError):
        logger.exception("CDF API error deleting container indexes")
        body: dict[str, Any] = {
            "error": "CogniteAPIError",
            "code": getattr(exc, "code", None),
            "message": str(exc),
        }
    else:
        logger.exception("Cognite error deleting container indexes")
        body = {"error": type(exc).__name__, "message": str(exc)}
    if completed_batches:
        body["completedBatches"] = completed_batches
        body["items"] = items
    return json.dumps(body)


def _access_on_forbidden(
    client: CogniteClient,
    exc: CogniteException,
    spaces: list[str],
) -> dict[str, Any] | None:
    if not isinstance(exc, CogniteAPIError) or getattr(exc, "code", None) != 403:
        return None
    return check_spaces(client, acl=MODELS_ACL, action="WRITE", spaces=spaces)


def delete_container_indexes(
    client: CogniteClient,
    *,
    indexes: list[dict[str, Any]] | str,
    dry_run: bool = DEFAULT_DRY_RUN,
) -> str:
    """Delete one or more indexes from containers.

    Index item example::
      {
        "space": "sp_x",
        "containerExternalId": "Asset",
        "identifier": "nameIndex"
      }

    ``externalId`` is accepted as an alias for ``containerExternalId``.
    ``index`` is accepted as an alias for ``identifier``.

    Defaults to ``DEFAULT_DRY_RUN`` (retrieve containers and report which
    requested indexes exist). Pass ``dry_run=false`` to delete. Requires
    ``dataModelsAcl:WRITE`` for an actual delete.

    Deletes are chunked to at most ``MAX_CONTAINER_INDEX_DELETE`` (10) ids per
    CDF call. If a later batch fails, the error includes ``completedBatches``
    and the index ids already deleted. Indexes cannot be edited in place —
    delete then re-apply the container with a new index definition via
    ``apply_containers``.
    """
    space_ids: list[str] = []
    try:
        raw = require_object_list(parse_object_list(indexes), label="index")
        refs = [_parse_index_ref(item) for item in raw]
        space_ids = [container_id.space for container_id, _ in refs]
        batches = chunk(refs, MAX_CONTAINER_INDEX_DELETE)

        if dry_run:
            # One retrieve per unique container so we can see which indexes exist.
            by_container: dict[tuple[str, str], list[str]] = {}
            for container_id, identifier in refs:
                key = (container_id.space, container_id.external_id)
                by_container.setdefault(key, []).append(identifier)

            existing_by_container: dict[tuple[str, str], set[str]] = {}
            container_payloads: list[dict[str, Any]] = []
            container_ids = [ContainerId(space, external_id) for space, external_id in by_container]
            for batch in chunk(container_ids, 100):
                retrieved = client.data_modeling.containers.retrieve(ids=batch)
                for container in as_list(retrieved):
                    key = (container.space, container.external_id)
                    existing_by_container[key] = _existing_index_names(container)
                    container_payloads.append(dump_schema(container))

            found: list[dict[str, str]] = []
            missing: list[dict[str, str]] = []
            for container_id, identifier in refs:
                key = (container_id.space, container_id.external_id)
                present = existing_by_container.get(key, set())
                item = _ref_dict((container_id, identifier))
                if identifier in present:
                    found.append(item)
                else:
                    missing.append(item)

            access = check_spaces(client, acl=MODELS_ACL, action="WRITE", spaces=space_ids)
            denied = is_denied(access)
            message = (
                "Dry run only — indexes were not deleted. "
                "Indexes cannot be edited in place; delete then apply a replacement."
            )
            if denied:
                message = f"{message} {denial_detail(access)}"
            return json.dumps(
                {
                    "dryRun": True,
                    "wouldDelete": bool(found) and not denied,
                    "requested": len(refs),
                    "found": len(found),
                    "missing": missing,
                    "batches": len(batches),
                    "maxBatchSize": MAX_CONTAINER_INDEX_DELETE,
                    "access": access,
                    "items": found,
                    "containers": container_payloads,
                    "message": message,
                },
                indent=2,
            )

        deleted_items: list[dict[str, str]] = []
        succeeded: list[dict[str, str]] = []
        completed_batches = 0
        for batch in batches:
            try:
                deleted = client.data_modeling.containers.delete_indexes(batch)
            except CogniteException as exc:
                return _partial_error(
                    exc,
                    completed_batches=completed_batches,
                    items=succeeded,
                )
            completed_batches += 1
            succeeded.extend(_ref_dict(ref) for ref in batch)
            for item in deleted or []:
                if isinstance(item, tuple) and len(item) == 2:
                    container_id, identifier = item
                    deleted_items.append(_ref_dict((container_id, str(identifier))))
        return json.dumps(
            {
                "dryRun": False,
                "deleted": bool(deleted_items or succeeded),
                "count": len(deleted_items) if deleted_items else len(succeeded),
                "batches": len(batches),
                "maxBatchSize": MAX_CONTAINER_INDEX_DELETE,
                "items": deleted_items or succeeded,
            },
            indent=2,
        )
    except (TypeError, ValueError, json.JSONDecodeError, KeyError) as exc:
        return json.dumps({"error": "InvalidArgument", "message": str(exc)})
    except CogniteAPIError as exc:
        logger.exception("CDF API error deleting container indexes")
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
        logger.exception("Cognite error deleting container indexes")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error deleting container indexes")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
