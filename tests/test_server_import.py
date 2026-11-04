"""Smoke: MCP server module loads and registers tools (no CDF network)."""

from __future__ import annotations

from cognite_cdf_mcp.tools.params import DEFAULT_DRY_RUN


def test_server_imports_and_registers_core_tools() -> None:
    from cognite_cdf_mcp.server import mcp

    tools = {t.name: t for t in mcp._tool_manager.list_tools()}
    assert "list_environments" in tools
    assert "use_environment" in tools
    assert "query_instances" in tools
    assert "get_filter_docs" in tools

    # CDF tools expose optional environment; filter docs does not call CDF.
    assert "environment" in tools["query_instances"].parameters["properties"]
    assert "environment" not in tools["get_filter_docs"].parameters.get("properties", {})
    assert "environment" not in tools["list_environments"].parameters.get("properties", {})

    # Write tools share DEFAULT_DRY_RUN (experimental safety switch).
    for name in (
        "apply_spaces",
        "delete_spaces",
        "apply_instances",
        "delete_instances",
        "delete_view",
    ):
        props = tools[name].parameters["properties"]
        assert props["dry_run"].get("default") is DEFAULT_DRY_RUN, name
