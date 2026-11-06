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

    # Session helpers are closed-world and readOnly so write-gated hosts still
    # allow env switching for query workflows.
    for name in ("list_environments", "use_environment"):
        ann = tools[name].annotations
        assert ann.read_only_hint is True, name
        assert ann.open_world_hint is False, name
        assert ann.destructive_hint is False, name
    assert tools["query_instances"].annotations.open_world_hint is True

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

    apply_doc = tools["apply_instances"].description or ""
    assert "replace=true" in apply_doc
    assert "clears omitted properties" in apply_doc
    assert "auto_create_direct_relations" in apply_doc
    assert "empty target nodes" in apply_doc
    assert tools["apply_instances"].annotations.destructive_hint is False

    aggregate = tools["aggregate_instances"]
    aggregate_doc = " ".join((aggregate.description or "").split())
    assert "operator" not in aggregate.parameters["properties"]
    assert "no operator parameter" in aggregate_doc
    assert "defaults to AND" in aggregate_doc

    for name in ("apply_spaces", "delete_spaces"):
        doc = tools[name].description or ""
        assert "100" in doc, name
        assert "completedBatches" in doc, name
    delete_spaces_doc = " ".join((tools["delete_spaces"].description or "").split())
    assert "does not validate dependency conflicts" in delete_spaces_doc
