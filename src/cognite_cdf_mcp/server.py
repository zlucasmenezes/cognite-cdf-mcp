"""CDF MCP server entrypoint (stdio / MCPServer)."""

from __future__ import annotations

import logging
import sys

from mcp.server.mcpserver import MCPServer

from cognite_cdf_mcp.cdf.client import get_cognite_client
from cognite_cdf_mcp.tools.list_data_models import list_data_models as _list_data_models
from cognite_cdf_mcp.tools.list_spaces import list_spaces as _list_spaces

# stdout is reserved for MCP JSON-RPC; keep all logs on stderr.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("cognite_cdf_mcp")

mcp = MCPServer("cognite-cdf-mcp", version="0.1.0")


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


def main() -> None:
    """Run the MCP server over stdio."""
    logger.info("Starting cognite-cdf-mcp (stdio)")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
