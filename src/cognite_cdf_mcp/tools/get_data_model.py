"""Tool: retrieve a specific CDF data model."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import DataModelId
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.errors import not_found_data_model
from cognite_cdf_mcp.tools.get_view import _serialize_view_detail

logger = logging.getLogger(__name__)


def _view_ref(view: Any) -> dict[str, Any]:
    return {
        "space": getattr(view, "space", None),
        "externalId": getattr(view, "external_id", None),
        "version": getattr(view, "version", None),
    }


def _serialize_view_entry(view: Any) -> dict[str, Any]:
    # With inline_views=True the SDK returns View objects (have properties).
    # With inline_views=False it returns ViewId refs only.
    if hasattr(view, "properties"):
        return _serialize_view_detail(view)
    return _view_ref(view)


def _serialize_data_model(model: Any) -> dict[str, Any]:
    views = getattr(model, "views", None) or []
    return {
        "space": model.space,
        "externalId": model.external_id,
        "version": model.version,
        "name": model.name,
        "description": model.description,
        "isGlobal": model.is_global,
        "createdTime": getattr(model, "created_time", None),
        "lastUpdatedTime": getattr(model, "last_updated_time", None),
        "views": [_serialize_view_entry(v) for v in views],
    }


def get_data_model(
    client: CogniteClient,
    *,
    space: str,
    external_id: str,
    version: str,
    inline_views: bool = False,
) -> str:
    """Retrieve one data model by space, externalId, and version.

    When ``inline_views`` is True, each entry in ``views`` includes the full
    view definition (properties, implements, etc.). When False, only view
    references (space / externalId / version) are returned.
    """
    try:
        models = client.data_modeling.data_models.retrieve(
            ids=DataModelId(space=space, external_id=external_id, version=version),
            inline_views=inline_views,
        )
        if not models:
            return json.dumps(
                not_found_data_model(
                    client,
                    space=space,
                    external_id=external_id,
                    version=version,
                ),
                indent=2,
            )
        return json.dumps(
            {
                "item": _serialize_data_model(models[0]),
                "inlineViews": inline_views,
            },
            indent=2,
        )
    except CogniteAPIError as exc:
        logger.exception("CDF API error retrieving data model")
        return json.dumps(
            {
                "error": "CogniteAPIError",
                "code": getattr(exc, "code", None),
                "message": str(exc),
            }
        )
    except CogniteException as exc:
        logger.exception("Cognite error retrieving data model")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error retrieving data model")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
