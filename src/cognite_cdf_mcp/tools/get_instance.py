"""Tool: retrieve one CDF instance (node or edge)."""

from __future__ import annotations

import json
import logging

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import EdgeId, NodeId
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.instances_common import (
    InstanceType,
    optional_view_id,
    serialize_instance,
)

logger = logging.getLogger(__name__)


def get_instance(
    client: CogniteClient,
    *,
    space: str,
    external_id: str,
    instance_type: InstanceType = "node",
    view_space: str | None = None,
    view_external_id: str | None = None,
    view_version: str | None = None,
    include_typing: bool = False,
) -> str:
    """Retrieve one instance by space and externalId.

    Optionally project properties through a view (``view_*``).
    Requires ``dataModelInstancesAcl:READ``.
    """
    try:
        sources = optional_view_id(
            view_space=view_space,
            view_external_id=view_external_id,
            view_version=view_version,
        )
        if instance_type == "edge":
            item = client.data_modeling.instances.retrieve_edges(
                edges=EdgeId(space=space, external_id=external_id),
                sources=sources,
                include_typing=include_typing,
            )
        else:
            item = client.data_modeling.instances.retrieve_nodes(
                nodes=NodeId(space=space, external_id=external_id),
                sources=sources,
                include_typing=include_typing,
            )

        if item is None:
            return json.dumps(
                {
                    "error": "NotFound",
                    "message": (
                        f"Instance not found: type={instance_type!r}, "
                        f"space={space!r}, externalId={external_id!r}"
                    ),
                }
            )

        return json.dumps({"item": serialize_instance(item)}, indent=2)
    except ValueError as exc:
        return json.dumps({"error": "InvalidArgument", "message": str(exc)})
    except CogniteAPIError as exc:
        logger.exception("CDF API error retrieving instance")
        return json.dumps(
            {
                "error": "CogniteAPIError",
                "code": getattr(exc, "code", None),
                "message": str(exc),
            }
        )
    except CogniteException as exc:
        logger.exception("Cognite error retrieving instance")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error retrieving instance")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
