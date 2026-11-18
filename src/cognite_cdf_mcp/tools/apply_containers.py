"""Tool: create/update CDF containers with dry-run."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import ContainerApply, ContainerId
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.access import MODELS_ACL, check_spaces, denial_detail, is_denied
from cognite_cdf_mcp.tools.params import (
    DEFAULT_DRY_RUN,
    MAX_INDEXES_PER_CONTAINER,
    MAX_SCHEMA_PER_REQUEST,
    parse_object_list,
)
from cognite_cdf_mcp.tools.schema_common import (
    as_list,
    dump_schema,
    partial_cognite_error,
    require_object_list,
    schema_batches,
)

logger = logging.getLogger(__name__)


def _parse_container(item: dict[str, Any]) -> ContainerApply:
    indexes = item.get("indexes")
    if isinstance(indexes, dict) and len(indexes) > MAX_INDEXES_PER_CONTAINER:
        external_id = item.get("externalId") or item.get("external_id") or "?"
        raise ValueError(
            f"container {external_id!r} has {len(indexes)} indexes; "
            f"CDF allows at most {MAX_INDEXES_PER_CONTAINER}"
        )
    try:
        return ContainerApply.load(item)
    except (TypeError, ValueError, KeyError) as exc:
        raise ValueError(f"invalid container: {exc}") from exc


def _container_ref(item: ContainerApply) -> dict[str, str]:
    return {"space": item.space, "externalId": item.external_id}


def _access_on_forbidden(
    client: CogniteClient,
    exc: CogniteException,
    spaces: list[str],
) -> dict[str, Any] | None:
    if not isinstance(exc, CogniteAPIError) or getattr(exc, "code", None) != 403:
        return None
    return check_spaces(client, acl=MODELS_ACL, action="WRITE", spaces=spaces)


def apply_containers(
    client: CogniteClient,
    *,
    containers: list[dict[str, Any]] | str,
    dry_run: bool = DEFAULT_DRY_RUN,
) -> str:
    """Create or update containers (upsert).

    Container item example::
      {
        "space": "sp_x",
        "externalId": "Asset",
        "usedFor": "node",
        "properties": {
          "name": {"type": {"type": "text", "list": false}, "nullable": true}
        },
        "indexes": {
          "nameIndex": {"indexType": "btree", "properties": ["name"]}
        }
      }

    New indexes are created through this apply (up to 10 per container). Existing
    indexes cannot be edited in place — delete them with
    ``delete_container_indexes``, then apply a replacement definition.

    Defaults to ``DEFAULT_DRY_RUN`` (retrieve existing; no write). Pass
    ``dry_run=false`` to apply. Requires ``dataModelsAcl:WRITE`` for an actual write.

    Apply and retrieve-by-ids send at most ``MAX_SCHEMA_PER_REQUEST`` (100)
    containers per CDF call. If a later batch fails, the error includes
    ``completedBatches`` and the container ids already applied.
    """
    space_ids: list[str] = []
    try:
        raw = require_object_list(parse_object_list(containers), label="container")
        applies = [_parse_container(item) for item in raw]
        space_ids = [item.space for item in applies]
        batches = schema_batches(applies)

        if dry_run:
            existing_list: list[Any] = []
            for batch in batches:
                existing = client.data_modeling.containers.retrieve(
                    ids=[ContainerId(item.space, item.external_id) for item in batch]
                )
                existing_list.extend(as_list(existing))
            access = check_spaces(client, acl=MODELS_ACL, action="WRITE", spaces=space_ids)
            denied = is_denied(access)
            message = "Dry run only — containers were not written."
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
                result = client.data_modeling.containers.apply(batch)
            except CogniteException as exc:
                return partial_cognite_error(
                    exc,
                    completed_batches=completed_batches,
                    items=succeeded,
                    action="applying containers",
                    access=_access_on_forbidden(client, exc, space_ids),
                )
            completed_batches += 1
            succeeded.extend(_container_ref(item) for item in batch)
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
        logger.exception("CDF API error applying containers")
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
        logger.exception("Cognite error applying containers")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error applying containers")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
