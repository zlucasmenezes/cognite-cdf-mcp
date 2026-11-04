"""Tool: retrieve a specific CDF view."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import ViewId
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.errors import not_found_view

logger = logging.getLogger(__name__)


def _serialize_property(name: str, prop: Any) -> dict[str, Any]:
    raw = prop.dump(camel_case=True) if hasattr(prop, "dump") else {"name": name}
    # Keep identifier explicit even if dump omits it.
    raw.setdefault("name", getattr(prop, "name", None) or name)
    return raw


def _serialize_view_detail(view: Any) -> dict[str, Any]:
    properties = getattr(view, "properties", None) or {}
    implements = getattr(view, "implements", None) or []
    return {
        "space": view.space,
        "externalId": view.external_id,
        "version": view.version,
        "name": view.name,
        "description": view.description,
        "usedFor": view.used_for,
        "isGlobal": view.is_global,
        "writable": getattr(view, "writable", None),
        "createdTime": getattr(view, "created_time", None),
        "lastUpdatedTime": getattr(view, "last_updated_time", None),
        "implements": [
            {
                "space": getattr(ref, "space", None),
                "externalId": getattr(ref, "external_id", None),
                "version": getattr(ref, "version", None),
            }
            for ref in implements
        ],
        "properties": {name: _serialize_property(name, prop) for name, prop in properties.items()},
    }


def get_view(
    client: CogniteClient,
    *,
    space: str,
    external_id: str,
    version: str,
    include_inherited_properties: bool = True,
) -> str:
    """Retrieve one view by space, externalId, and version."""
    try:
        views = client.data_modeling.views.retrieve(
            ids=ViewId(space=space, external_id=external_id, version=version),
            include_inherited_properties=include_inherited_properties,
        )
        if not views:
            return json.dumps(
                not_found_view(
                    client,
                    space=space,
                    external_id=external_id,
                    version=version,
                ),
                indent=2,
            )
        payload = {"item": _serialize_view_detail(views[0])}
        return json.dumps(payload, indent=2)
    except CogniteAPIError as exc:
        logger.exception("CDF API error retrieving view")
        return json.dumps(
            {
                "error": "CogniteAPIError",
                "code": getattr(exc, "code", None),
                "message": str(exc),
            }
        )
    except CogniteException as exc:
        logger.exception("Cognite error retrieving view")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error retrieving view")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
