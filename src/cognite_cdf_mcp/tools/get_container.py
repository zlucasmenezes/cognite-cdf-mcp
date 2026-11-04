"""Tool: retrieve one CDF container."""

from __future__ import annotations

import json
import logging
from typing import Any

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import ContainerId
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.errors import not_found_container

logger = logging.getLogger(__name__)


def get_container(
    client: CogniteClient,
    *,
    space: str,
    external_id: str,
) -> str:
    """Retrieve one container by space and externalId."""
    try:
        container = client.data_modeling.containers.retrieve(
            ids=ContainerId(space=space, external_id=external_id),
        )
        if container is None:
            return json.dumps(
                not_found_container(client, space=space, external_id=external_id),
                indent=2,
            )
        # retrieve may return a list when multiple ids are used; single id → object
        if hasattr(container, "__iter__") and not hasattr(container, "dump"):
            items = list(container)
            if not items:
                return json.dumps(
                    not_found_container(client, space=space, external_id=external_id),
                    indent=2,
                )
            container = items[0]

        payload: dict[str, Any] = (
            container.dump(camel_case=True)
            if hasattr(container, "dump")
            else {
                "space": getattr(container, "space", None),
                "externalId": getattr(container, "external_id", None),
            }
        )
        return json.dumps({"item": payload}, indent=2)
    except CogniteAPIError as exc:
        logger.exception("CDF API error retrieving container")
        return json.dumps(
            {
                "error": "CogniteAPIError",
                "code": getattr(exc, "code", None),
                "message": str(exc),
            }
        )
    except CogniteException as exc:
        logger.exception("Cognite error retrieving container")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error retrieving container")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
