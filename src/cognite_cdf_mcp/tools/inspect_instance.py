"""Tool: inspect involved views/containers for one instance."""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import EdgeId, NodeId
from cognite.client.data_classes.data_modeling.instances import (
    InvolvedContainers,
    InvolvedViews,
)
from cognite.client.exceptions import CogniteAPIError, CogniteException

from cognite_cdf_mcp.tools.errors import not_found_instance

logger = logging.getLogger(__name__)

InstanceType = Literal["node", "edge"]


def inspect_instance(
    client: CogniteClient,
    *,
    space: str,
    external_id: str,
    instance_type: InstanceType = "node",
    all_versions: bool = False,
) -> str:
    """Return involved views and containers for one node/edge.

    Requires ``dataModelInstancesAcl:READ``.
    """
    try:
        if instance_type == "edge":
            result = client.data_modeling.instances.inspect(
                edges=EdgeId(space=space, external_id=external_id),
                involved_views=InvolvedViews(all_versions=all_versions),
                involved_containers=InvolvedContainers(),
            )
            items = list(result.edges) if result is not None else []
        else:
            result = client.data_modeling.instances.inspect(
                nodes=NodeId(space=space, external_id=external_id),
                involved_views=InvolvedViews(all_versions=all_versions),
                involved_containers=InvolvedContainers(),
            )
            items = list(result.nodes) if result is not None else []

        if not items:
            return json.dumps(
                not_found_instance(
                    client,
                    space=space,
                    external_id=external_id,
                    instance_type=instance_type,
                ),
                indent=2,
            )

        item = items[0]
        payload: dict[str, Any] = (
            item.dump(camel_case=True) if hasattr(item, "dump") else {"space": space}
        )
        return json.dumps({"item": payload}, indent=2)
    except CogniteAPIError as exc:
        logger.exception("CDF API error inspecting instance")
        return json.dumps(
            {
                "error": "CogniteAPIError",
                "code": getattr(exc, "code", None),
                "message": str(exc),
            }
        )
    except CogniteException as exc:
        logger.exception("Cognite error inspecting instance")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error inspecting instance")
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})
