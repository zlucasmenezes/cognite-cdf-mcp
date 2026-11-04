"""CDF MCP server entrypoint (stdio / MCPServer)."""

from __future__ import annotations

import logging
import sys
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from cognite_cdf_mcp.cdf.client import get_cognite_client
from cognite_cdf_mcp.tools.aggregate_instances import (
    aggregate_instances as _aggregate_instances,
)
from cognite_cdf_mcp.tools.apply_instances import apply_instances as _apply_instances
from cognite_cdf_mcp.tools.apply_spaces import apply_spaces as _apply_spaces
from cognite_cdf_mcp.tools.delete_instances import delete_instances as _delete_instances
from cognite_cdf_mcp.tools.delete_spaces import delete_spaces as _delete_spaces
from cognite_cdf_mcp.tools.delete_view import delete_view as _delete_view
from cognite_cdf_mcp.tools.get_container import get_container as _get_container
from cognite_cdf_mcp.tools.get_data_model import get_data_model as _get_data_model
from cognite_cdf_mcp.tools.get_filter_docs import get_filter_docs as _get_filter_docs
from cognite_cdf_mcp.tools.get_instance import get_instance as _get_instance
from cognite_cdf_mcp.tools.get_space import get_space as _get_space
from cognite_cdf_mcp.tools.get_view import get_view as _get_view
from cognite_cdf_mcp.tools.inspect_instance import inspect_instance as _inspect_instance
from cognite_cdf_mcp.tools.list_containers import list_containers as _list_containers
from cognite_cdf_mcp.tools.list_data_models import list_data_models as _list_data_models
from cognite_cdf_mcp.tools.list_spaces import list_spaces as _list_spaces
from cognite_cdf_mcp.tools.list_views import list_views as _list_views
from cognite_cdf_mcp.tools.params import DEFAULT_LIMIT
from cognite_cdf_mcp.tools.query_instances import query_instances as _query_instances
from cognite_cdf_mcp.tools.search_instances import search_instances as _search_instances

# stdout is reserved for MCP JSON-RPC; keep all logs on stderr.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("cognite_cdf_mcp")

mcp = MCPServer("cognite-cdf-mcp", version="0.1.0")

READ_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)
WRITE_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
    openWorldHint=True,
)
# create/update without deleting existing instances
UPSERT_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=True,
)


# --- Reads -----------------------------------------------------------------


@mcp.tool(title="List data models", annotations=READ_ANNOTATIONS)
def list_data_models(
    space: str | None = None,
    all_versions: bool = False,
    include_global: bool = False,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> str:
    """List data models in the CDF project (lean metadata + view refs).

    Requires dataModelsAcl:READ. Default limit is 100.
    Returns nextCursor when more pages are available.
    """
    client = get_cognite_client()
    return _list_data_models(
        client,
        space=space,
        all_versions=all_versions,
        include_global=include_global,
        limit=limit,
        cursor=cursor,
    )


@mcp.tool(title="Get data model", annotations=READ_ANNOTATIONS)
def get_data_model(
    space: str,
    external_id: str,
    version: str,
    inline_views: bool = False,
) -> str:
    """Retrieve a specific data model by space, externalId, and version.

    Requires dataModelsAcl:READ.
    inline_views=false: views as refs (space/externalId/version).
    inline_views=true: each view expanded with properties and implements.
    """
    client = get_cognite_client()
    return _get_data_model(
        client,
        space=space,
        external_id=external_id,
        version=version,
        inline_views=inline_views,
    )


@mcp.tool(title="List spaces", annotations=READ_ANNOTATIONS)
def list_spaces(
    include_global: bool = False,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> str:
    """List spaces in the CDF project.

    Requires dataModelsAcl:READ. Default limit is 100.
    Returns nextCursor when more pages are available.
    """
    client = get_cognite_client()
    return _list_spaces(
        client,
        include_global=include_global,
        limit=limit,
        cursor=cursor,
    )


@mcp.tool(title="Get space", annotations=READ_ANNOTATIONS)
def get_space(space: str) -> str:
    """Retrieve a specific space by id.

    Requires dataModelsAcl:READ.
    """
    client = get_cognite_client()
    return _get_space(client, space=space)


@mcp.tool(title="List views", annotations=READ_ANNOTATIONS)
def list_views(
    space: str | None = None,
    all_versions: bool = False,
    include_global: bool = False,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> str:
    """List views in the CDF project (lean metadata, no full property dump).

    Requires dataModelsAcl:READ. Prefer filtering by space for large projects.
    Default limit is 100. Returns nextCursor when more pages are available.
    """
    client = get_cognite_client()
    return _list_views(
        client,
        space=space,
        all_versions=all_versions,
        include_global=include_global,
        limit=limit,
        cursor=cursor,
    )


@mcp.tool(title="Get view", annotations=READ_ANNOTATIONS)
def get_view(
    space: str,
    external_id: str,
    version: str,
    include_inherited_properties: bool = True,
) -> str:
    """Retrieve a specific view by space, externalId, and version.

    Requires dataModelsAcl:READ. Returns view metadata and property definitions.
    """
    client = get_cognite_client()
    return _get_view(
        client,
        space=space,
        external_id=external_id,
        version=version,
        include_inherited_properties=include_inherited_properties,
    )


@mcp.tool(title="List containers", annotations=READ_ANNOTATIONS)
def list_containers(
    space: str | None = None,
    include_global: bool = False,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> str:
    """List containers in the CDF project (lean metadata).

    Requires dataModelsAcl:READ. Default limit is 100.
    Returns nextCursor when more pages are available.
    """
    client = get_cognite_client()
    return _list_containers(
        client,
        space=space,
        include_global=include_global,
        limit=limit,
        cursor=cursor,
    )


@mcp.tool(title="Get container", annotations=READ_ANNOTATIONS)
def get_container(
    space: str,
    external_id: str,
) -> str:
    """Retrieve one container by space and externalId.

    Requires dataModelsAcl:READ.
    """
    client = get_cognite_client()
    return _get_container(client, space=space, external_id=external_id)


@mcp.tool(title="Filter DSL docs", annotations=READ_ANNOTATIONS)
def get_filter_docs() -> str:
    """Return CDF instance filter DSL examples and property-path tips.

    Use before writing filters for query_instances / search_instances /
    aggregate_instances.
    """
    return _get_filter_docs()


@mcp.tool(title="Get instance", annotations=READ_ANNOTATIONS)
def get_instance(
    space: str,
    external_id: str,
    instance_type: Literal["node", "edge"] = "node",
    view_space: str | None = None,
    view_external_id: str | None = None,
    view_version: str | None = None,
    include_typing: bool = False,
) -> str:
    """Retrieve one instance (node or edge) by space and externalId.

    Requires dataModelInstancesAcl:READ.
    Optionally set view_space / view_external_id / view_version together to
    project properties through that view.
    """
    client = get_cognite_client()
    return _get_instance(
        client,
        space=space,
        external_id=external_id,
        instance_type=instance_type,
        view_space=view_space,
        view_external_id=view_external_id,
        view_version=view_version,
        include_typing=include_typing,
    )


@mcp.tool(title="Inspect instance", annotations=READ_ANNOTATIONS)
def inspect_instance(
    space: str,
    external_id: str,
    instance_type: Literal["node", "edge"] = "node",
    all_versions: bool = False,
) -> str:
    """Inspect which views and containers an instance is involved in.

    Requires dataModelInstancesAcl:READ. Useful when get_instance returns empty
    properties or you need to discover the right view projection.
    """
    client = get_cognite_client()
    return _inspect_instance(
        client,
        space=space,
        external_id=external_id,
        instance_type=instance_type,
        all_versions=all_versions,
    )


@mcp.tool(title="Query instances", annotations=READ_ANNOTATIONS)
def query_instances(
    view_space: str,
    view_external_id: str,
    view_version: str,
    instance_space: str | None = None,
    instance_type: Literal["node", "edge"] = "node",
    filter: dict[str, Any] | str | None = None,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
    include_typing: bool = False,
) -> str:
    """Query instances through a view, with optional space, CDF filter, and cursor.

    Requires dataModelInstancesAcl:READ. Default limit is 100.
    Returns nextCursor when more pages are available.
    Call get_filter_docs for filter examples.
    """
    client = get_cognite_client()
    return _query_instances(
        client,
        view_space=view_space,
        view_external_id=view_external_id,
        view_version=view_version,
        instance_space=instance_space,
        instance_type=instance_type,
        filter=filter,
        limit=limit,
        cursor=cursor,
        include_typing=include_typing,
    )


@mcp.tool(title="Search instances", annotations=READ_ANNOTATIONS)
def search_instances(
    view_space: str,
    view_external_id: str,
    view_version: str,
    query: str,
    properties: list[str] | None = None,
    instance_space: str | None = None,
    instance_type: Literal["node", "edge"] = "node",
    filter: dict[str, Any] | str | None = None,
    limit: int = DEFAULT_LIMIT,
    include_typing: bool = False,
) -> str:
    """Full-text search instances through a view (name, aliases, etc.).

    Requires dataModelInstancesAcl:READ. Default limit is 100.
    """
    client = get_cognite_client()
    return _search_instances(
        client,
        view_space=view_space,
        view_external_id=view_external_id,
        view_version=view_version,
        query=query,
        properties=properties,
        instance_space=instance_space,
        instance_type=instance_type,
        filter=filter,
        limit=limit,
        include_typing=include_typing,
    )


@mcp.tool(title="Aggregate instances", annotations=READ_ANNOTATIONS)
def aggregate_instances(
    view_space: str,
    view_external_id: str,
    view_version: str,
    aggregates: list[dict[str, Any]] | dict[str, Any] | str,
    group_by: list[str] | str | None = None,
    instance_space: str | None = None,
    instance_type: Literal["node", "edge"] = "node",
    query: str | None = None,
    filter: dict[str, Any] | str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> str:
    """Aggregate instances (count/sum/avg/min/max) through a view.

    Requires dataModelInstancesAcl:READ.
    aggregates example: {"count": {"property": "externalId"}}
    """
    client = get_cognite_client()
    return _aggregate_instances(
        client,
        view_space=view_space,
        view_external_id=view_external_id,
        view_version=view_version,
        aggregates=aggregates,
        group_by=group_by,
        instance_space=instance_space,
        instance_type=instance_type,
        query=query,
        filter=filter,
        limit=limit,
    )


# --- Writes ----------------------------------------------------------------


@mcp.tool(title="Apply spaces", annotations=UPSERT_ANNOTATIONS)
def apply_spaces(
    spaces: list[dict[str, Any]] | str,
    dry_run: bool = False,
) -> str:
    """Create or update spaces (upsert).

    Requires dataModelsAcl:WRITE for an actual apply.
    dry_run=true validates payloads and reports existing spaces (no write).
    spaces example: [{"space": "sp_x", "name": "Sandbox", "description": "..."}]
    """
    client = get_cognite_client()
    return _apply_spaces(client, spaces=spaces, dry_run=dry_run)


@mcp.tool(title="Delete spaces", annotations=WRITE_ANNOTATIONS)
def delete_spaces(
    spaces: list[str | dict[str, Any]] | str,
    dry_run: bool = False,
) -> str:
    """Delete one or more spaces by id.

    Requires dataModelsAcl:WRITE for an actual delete.
    dry_run=true retrieves matching spaces only (no delete).
    spaces example: ["sp_x"] or [{"space": "sp_x"}]
    """
    client = get_cognite_client()
    return _delete_spaces(client, spaces=spaces, dry_run=dry_run)


@mcp.tool(title="Apply instances", annotations=UPSERT_ANNOTATIONS)
def apply_instances(
    nodes: list[dict[str, Any]] | str | None = None,
    edges: list[dict[str, Any]] | str | None = None,
    replace: bool = False,
    auto_create_direct_relations: bool = True,
    dry_run: bool = False,
) -> str:
    """Create or update instances (upsert nodes/edges).

    Requires dataModelInstancesAcl:WRITE for an actual apply.
    dry_run=true validates payloads and reports existing instances (no write).
    """
    client = get_cognite_client()
    return _apply_instances(
        client,
        nodes=nodes,
        edges=edges,
        replace=replace,
        auto_create_direct_relations=auto_create_direct_relations,
        dry_run=dry_run,
    )


@mcp.tool(title="Delete instances", annotations=WRITE_ANNOTATIONS)
def delete_instances(
    items: list[dict[str, Any]] | str,
    instance_type: Literal["node", "edge"] = "node",
    dry_run: bool = False,
) -> str:
    """Delete one or more instances by space/externalId.

    Requires dataModelInstancesAcl:WRITE for an actual delete.
    dry_run=true retrieves matching instances only (no delete).
    items example: [{"space": "sp_x", "externalId": "MCH-1"}]
    """
    client = get_cognite_client()
    return _delete_instances(
        client,
        items=items,
        instance_type=instance_type,
        dry_run=dry_run,
    )


@mcp.tool(title="Delete view", annotations=WRITE_ANNOTATIONS)
def delete_view(
    space: str,
    external_id: str,
    version: str,
    dry_run: bool = False,
) -> str:
    """Delete a specific view by space, externalId, and version.

    Requires dataModelsAcl:WRITE for an actual delete.
    dry_run=true: only checks that the view exists and reports what would be
    deleted (no write; dependency conflicts are not validated).
    dry_run=false: permanently removes the view version from the project.
    """
    client = get_cognite_client()
    return _delete_view(
        client,
        space=space,
        external_id=external_id,
        version=version,
        dry_run=dry_run,
    )


def main() -> None:
    """Run the MCP server over stdio."""
    logger.info("Starting cognite-cdf-mcp (stdio)")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
