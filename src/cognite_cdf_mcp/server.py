"""CDF MCP server entrypoint (stdio / MCPServer)."""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Callable
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from cognite_cdf_mcp import __version__
from cognite_cdf_mcp.cdf.client import effective_environment, get_cognite_client
from cognite_cdf_mcp.config import UnknownEnvironmentError, resolve_environment
from cognite_cdf_mcp.tools import environments as _environments
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
from cognite_cdf_mcp.tools.params import DEFAULT_DRY_RUN, DEFAULT_LIMIT
from cognite_cdf_mcp.tools.query_instances import query_instances as _query_instances
from cognite_cdf_mcp.tools.search_instances import search_instances as _search_instances

# stdout is reserved for MCP JSON-RPC; keep all logs on stderr.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("cognite_cdf_mcp")

mcp = MCPServer("cognite-cdf-mcp", version=__version__)

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
# Local session helpers (no CDF / network). Treated as read-only so hosts that
# disable write tools still allow environment listing and switching for queries.
SESSION_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


def _call(environment: str | None, fn: Callable[..., str], /, **kwargs: Any) -> str:
    """Run a tool implementation against the resolved environment's client.

    ``environment`` overrides the session default. Unknown aliases / bad config come
    back as a JSON error. JSON-object results get ``environment`` and ``project`` added.
    """
    try:
        env_name = effective_environment(environment)
        project = resolve_environment(env_name).cdf_project
        client = get_cognite_client(environment)
    except UnknownEnvironmentError as exc:
        return json.dumps(_environments.unknown_environment_error(exc), indent=2)
    except ValueError as exc:
        return json.dumps({"error": "InvalidEnvironment", "message": str(exc)}, indent=2)

    result = fn(client, **kwargs)
    try:
        payload = json.loads(result)
    except (TypeError, ValueError):
        return result
    if isinstance(payload, dict):
        payload = {"environment": env_name, "project": project, **payload}
        return json.dumps(payload, indent=2)
    return result


# --- Environments ----------------------------------------------------------


@mcp.tool(title="List environments", annotations=SESSION_ANNOTATIONS)
def list_environments() -> str:
    """List configured CDF environments (default + CDF_PROJECT_<ALIAS> aliases).

    Shows project/cluster per alias and which one is active for this session.
    Tokens are never returned. Does not call CDF.
    """
    return _environments.list_environments()


@mcp.tool(title="Use environment", annotations=SESSION_ANNOTATIONS)
def use_environment(name: str) -> str:
    """Set the session default environment for all CDF tools (e.g. dev, qa, prod, default).

    Any tool can still override per call with its `environment` argument.
    Pagination cursors are project-scoped: re-query after switching.
    Does not call CDF (session-only; safe with write tools disabled).
    """
    return _environments.use_environment(name)


# --- Reads -----------------------------------------------------------------


@mcp.tool(title="List data models", annotations=READ_ANNOTATIONS)
def list_data_models(
    space: str | None = None,
    all_versions: bool = False,
    include_global: bool = False,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
    environment: str | None = None,
) -> str:
    """List data models in the CDF project (lean metadata + view refs).

    Requires dataModelsAcl:READ. Default limit is 100.
    Returns nextCursor when more pages are available.

    environment: optional alias from list_environments (default: session environment;
    see use_environment).
    """
    return _call(
        environment,
        _list_data_models,
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
    environment: str | None = None,
) -> str:
    """Retrieve a specific data model by space, externalId, and version.

    Requires dataModelsAcl:READ.
    inline_views=false: views as refs (space/externalId/version).
    inline_views=true: each view expanded with properties and implements.

    environment: optional alias from list_environments (default: session environment;
    see use_environment).
    """
    return _call(
        environment,
        _get_data_model,
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
    environment: str | None = None,
) -> str:
    """List spaces in the CDF project.

    Requires dataModelsAcl:READ. Default limit is 100.
    Returns nextCursor when more pages are available.

    environment: optional alias from list_environments (default: session environment;
    see use_environment).
    """
    return _call(
        environment,
        _list_spaces,
        include_global=include_global,
        limit=limit,
        cursor=cursor,
    )


@mcp.tool(title="Get space", annotations=READ_ANNOTATIONS)
def get_space(space: str, environment: str | None = None) -> str:
    """Retrieve a specific space by id.

    Requires dataModelsAcl:READ.

    environment: optional alias from list_environments (default: session environment;
    see use_environment).
    """
    return _call(environment, _get_space, space=space)


@mcp.tool(title="List views", annotations=READ_ANNOTATIONS)
def list_views(
    space: str | None = None,
    all_versions: bool = False,
    include_global: bool = False,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
    environment: str | None = None,
) -> str:
    """List views in the CDF project (lean metadata, no full property dump).

    Requires dataModelsAcl:READ. Prefer filtering by space for large projects.
    Default limit is 100. Returns nextCursor when more pages are available.

    environment: optional alias from list_environments (default: session environment;
    see use_environment).
    """
    return _call(
        environment,
        _list_views,
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
    environment: str | None = None,
) -> str:
    """Retrieve a specific view by space, externalId, and version.

    Requires dataModelsAcl:READ. Returns view metadata and property definitions.

    environment: optional alias from list_environments (default: session environment;
    see use_environment).
    """
    return _call(
        environment,
        _get_view,
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
    environment: str | None = None,
) -> str:
    """List containers in the CDF project (lean metadata).

    Requires dataModelsAcl:READ. Default limit is 100.
    Returns nextCursor when more pages are available.

    environment: optional alias from list_environments (default: session environment;
    see use_environment).
    """
    return _call(
        environment,
        _list_containers,
        space=space,
        include_global=include_global,
        limit=limit,
        cursor=cursor,
    )


@mcp.tool(title="Get container", annotations=READ_ANNOTATIONS)
def get_container(
    space: str,
    external_id: str,
    environment: str | None = None,
) -> str:
    """Retrieve one container by space and externalId.

    Requires dataModelsAcl:READ.

    environment: optional alias from list_environments (default: session environment;
    see use_environment).
    """
    return _call(environment, _get_container, space=space, external_id=external_id)


@mcp.tool(title="Filter DSL docs", annotations=READ_ANNOTATIONS)
def get_filter_docs() -> str:
    """Return CDF instance filter DSL examples, limits, and search-vs-query tips.

    Use before writing filters for query_instances / search_instances /
    aggregate_instances. Covers in-filter ≤1000, apply/delete batching,
    AND/OR search, and the search-then-query discovery pattern.
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
    environment: str | None = None,
) -> str:
    """Retrieve one instance (node or edge) by space and externalId.

    Requires dataModelInstancesAcl:READ.
    Optionally set view_space / view_external_id / view_version together to
    project properties through that view.

    environment: optional alias from list_environments (default: session environment;
    see use_environment).
    """
    return _call(
        environment,
        _get_instance,
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
    environment: str | None = None,
) -> str:
    """Inspect which views and containers an instance is involved in.

    Requires dataModelInstancesAcl:READ. Useful when get_instance returns empty
    properties or you need to discover the right view projection.

    environment: optional alias from list_environments (default: session environment;
    see use_environment).
    """
    return _call(
        environment,
        _inspect_instance,
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
    properties: list[str] | None = None,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
    include_typing: bool = False,
    environment: str | None = None,
) -> str:
    """Exact-match query through a view (filter, space, cursor, properties).

    Requires dataModelInstancesAcl:READ. Default limit is 100.
    Returns nextCursor when more pages are available.
    Prefer properties=[…] over fetching all fields when hydrating candidates.
    For free-text discovery use search_instances first, then query with in on
    externalIds (see get_filter_docs). in filters accept ≤1000 values.

    environment: optional alias from list_environments (default: session environment;
    see use_environment).
    """
    return _call(
        environment,
        _query_instances,
        view_space=view_space,
        view_external_id=view_external_id,
        view_version=view_version,
        instance_space=instance_space,
        instance_type=instance_type,
        filter=filter,
        properties=properties,
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
    operator: Literal["AND", "OR"] = "AND",
    limit: int = DEFAULT_LIMIT,
    include_typing: bool = False,
    environment: str | None = None,
) -> str:
    """Full-text search through a view (name, aliases, etc.).

    Requires dataModelInstancesAcl:READ. Default limit is 100.
    operator=AND (default) for specific lookups; operator=OR for exploratory
    / typeahead. Combine with filter for exact constraints. After discovery,
    hydrate with query_instances (search-then-query).

    environment: optional alias from list_environments (default: session environment;
    see use_environment).
    """
    return _call(
        environment,
        _search_instances,
        view_space=view_space,
        view_external_id=view_external_id,
        view_version=view_version,
        query=query,
        properties=properties,
        instance_space=instance_space,
        instance_type=instance_type,
        filter=filter,
        operator=operator,
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
    environment: str | None = None,
) -> str:
    """Aggregate instances (count/sum/avg/min/max) through a view.

    Requires dataModelInstancesAcl:READ.
    aggregates example: {"count": {"property": "externalId"}}

    environment: optional alias from list_environments (default: session environment;
    see use_environment).
    """
    return _call(
        environment,
        _aggregate_instances,
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
    dry_run: bool = DEFAULT_DRY_RUN,
    environment: str | None = None,
) -> str:
    """Create or update spaces (upsert).

    Requires dataModelsAcl:WRITE for an actual apply.
    Defaults to dry_run=true (preview only); pass dry_run=false to write.
    spaces example: [{"space": "sp_x", "name": "Sandbox", "description": "..."}]

    environment: optional alias from list_environments (default: session environment;
    see use_environment).
    """
    return _call(environment, _apply_spaces, spaces=spaces, dry_run=dry_run)


@mcp.tool(title="Delete spaces", annotations=WRITE_ANNOTATIONS)
def delete_spaces(
    spaces: list[str | dict[str, Any]] | str,
    dry_run: bool = DEFAULT_DRY_RUN,
    environment: str | None = None,
) -> str:
    """Delete one or more spaces by id.

    Requires dataModelsAcl:WRITE for an actual delete.
    Defaults to dry_run=true (preview only); pass dry_run=false to delete.
    spaces example: ["sp_x"] or [{"space": "sp_x"}]

    environment: optional alias from list_environments (default: session environment;
    see use_environment).
    """
    return _call(environment, _delete_spaces, spaces=spaces, dry_run=dry_run)


@mcp.tool(title="Apply instances", annotations=UPSERT_ANNOTATIONS)
def apply_instances(
    nodes: list[dict[str, Any]] | str | None = None,
    edges: list[dict[str, Any]] | str | None = None,
    replace: bool = False,
    auto_create_direct_relations: bool = True,
    dry_run: bool = DEFAULT_DRY_RUN,
    environment: str | None = None,
) -> str:
    """Create or update instances (upsert nodes/edges).

    Requires dataModelInstancesAcl:WRITE for an actual apply.
    Defaults to dry_run=true (preview only); pass dry_run=false to write.
    Automatically chunks to ≤1000 nodes/edges per CDF apply call.

    environment: optional alias from list_environments (default: session environment;
    see use_environment).
    """
    return _call(
        environment,
        _apply_instances,
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
    dry_run: bool = DEFAULT_DRY_RUN,
    environment: str | None = None,
) -> str:
    """Delete one or more instances by space/externalId.

    Requires dataModelInstancesAcl:WRITE for an actual delete.
    Defaults to dry_run=true (preview only); pass dry_run=false to delete.
    Automatically chunks to ≤1000 ids per CDF delete call.
    items example: [{"space": "sp_x", "externalId": "MCH-1"}]

    environment: optional alias from list_environments (default: session environment;
    see use_environment).
    """
    return _call(
        environment,
        _delete_instances,
        items=items,
        instance_type=instance_type,
        dry_run=dry_run,
    )


@mcp.tool(title="Delete view", annotations=WRITE_ANNOTATIONS)
def delete_view(
    space: str,
    external_id: str,
    version: str,
    dry_run: bool = DEFAULT_DRY_RUN,
    environment: str | None = None,
) -> str:
    """Delete a specific view by space, externalId, and version.

    Requires dataModelsAcl:WRITE for an actual delete.
    Defaults to dry_run=true (preview only; dependency conflicts are not validated).
    Pass dry_run=false to permanently remove the view version from the project.

    environment: optional alias from list_environments (default: session environment;
    see use_environment).
    """
    return _call(
        environment,
        _delete_view,
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
