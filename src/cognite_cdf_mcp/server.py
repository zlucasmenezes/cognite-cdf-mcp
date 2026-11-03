"""CDF MCP server entrypoint (stdio / MCPServer)."""

from __future__ import annotations

import logging
import sys

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from cognite_cdf_mcp.cdf.client import get_cognite_client
from cognite_cdf_mcp.tools.delete_view import delete_view as _delete_view
from cognite_cdf_mcp.tools.get_data_model import get_data_model as _get_data_model
from cognite_cdf_mcp.tools.get_space import get_space as _get_space
from cognite_cdf_mcp.tools.get_view import get_view as _get_view
from cognite_cdf_mcp.tools.list_data_models import list_data_models as _list_data_models
from cognite_cdf_mcp.tools.list_spaces import list_spaces as _list_spaces
from cognite_cdf_mcp.tools.list_views import list_views as _list_views

# stdout is reserved for MCP JSON-RPC; keep all logs on stderr.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("cognite_cdf_mcp")

mcp = MCPServer("cognite-cdf-mcp", version="0.1.0")

WRITE_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
    openWorldHint=True,
)


@mcp.tool()
def list_data_models(
    space: str | None = None,
    all_versions: bool = False,
    include_global: bool = False,
    limit: int | None = None,
) -> str:
    """List data models in the CDF project (lean metadata + view refs).

    Requires dataModelsAcl:READ. Set limit to None to return all items.
    """
    client = get_cognite_client()
    return _list_data_models(
        client,
        space=space,
        all_versions=all_versions,
        include_global=include_global,
        limit=limit,
    )


@mcp.tool()
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


@mcp.tool()
def list_spaces(
    include_global: bool = False,
    limit: int | None = None,
) -> str:
    """List spaces in the CDF project.

    Requires dataModelsAcl:READ. Set limit to None to return all items.
    """
    client = get_cognite_client()
    return _list_spaces(
        client,
        include_global=include_global,
        limit=limit,
    )


@mcp.tool()
def get_space(space: str) -> str:
    """Retrieve a specific space by id.

    Requires dataModelsAcl:READ.
    """
    client = get_cognite_client()
    return _get_space(client, space=space)


@mcp.tool()
def list_views(
    space: str | None = None,
    all_versions: bool = False,
    include_global: bool = False,
    limit: int | None = None,
) -> str:
    """List views in the CDF project (lean metadata, no full property dump).

    Requires dataModelsAcl:READ. Prefer filtering by space for large projects.
    Set limit to None to return all items.
    """
    client = get_cognite_client()
    return _list_views(
        client,
        space=space,
        all_versions=all_versions,
        include_global=include_global,
        limit=limit,
    )


@mcp.tool()
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


@mcp.tool(annotations=WRITE_ANNOTATIONS)
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
