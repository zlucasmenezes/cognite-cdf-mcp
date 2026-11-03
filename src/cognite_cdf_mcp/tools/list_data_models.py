"""Tool: list CDF data models."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.exceptions import CogniteAPIError, CogniteException

logger = logging.getLogger(__name__)


def _view_ref(view: Any) -> dict[str, Any]:
    return {
        "space": getattr(view, "space", None),
        "externalId": getattr(view, "external_id", None),
        "version": getattr(view, "version", None),
    }


def _serialize_data_model(model: Any) -> dict[str, Any]:
    views = getattr(model, "views", None) or []
    return {
        "space": model.space,
        "externalId": model.external_id,
        "version": model.version,
        "name": model.name,
        "description": model.description,
        "isGlobal": model.is_global,
        "views": [_view_ref(v) for v in views],
    }


def list_data_models(
    client: CogniteClient,
    *,
    space: str | None = None,
    all_versions: bool = False,
    include_global: bool = False,
    limit: int | None = None,
) -> str:
    """List data models in the CDF project.

    Returns a JSON string with lean model metadata and view references
    (without inlined view definitions).
    """
    try:
        models = client.data_modeling.data_models.list(
            space=space,
            all_versions=all_versions,
            include_global=include_global,
            inline_views=False,
            limit=limit,
        )
        payload = {
            "count": len(models),
            "items": [_serialize_data_model(m) for m in models],
        }
        return json.dumps(payload, indent=2)
    except CogniteAPIError as exc:
        logger.exception("CDF API error listing data models")
        return json.dumps(
            {
                "error": "CogniteAPIError",
                "code": exc.code,
                "message": str(exc),
            }
        )
    except CogniteException as exc:
        logger.exception("Cognite error listing data models")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
