"""Unit tests for params helpers (DM limits alignment)."""

from __future__ import annotations

import json

import pytest

from cognite_cdf_mcp.tools.get_filter_docs import get_filter_docs
from cognite_cdf_mcp.tools.params import (
    MAX_IN_FILTER_VALUES,
    MAX_INSTANCE_WRITE_BATCH,
    chunk,
    parse_filter,
)


def test_chunk_splits_evenly() -> None:
    assert chunk(list(range(5)), 2) == [[0, 1], [2, 3], [4]]
    assert chunk([], 10) == []
    assert chunk([1, 2, 3], 1000) == [[1, 2, 3]]


def test_chunk_rejects_non_positive_size() -> None:
    with pytest.raises(ValueError, match="positive"):
        chunk([1], 0)


def test_parse_filter_rejects_oversized_in() -> None:
    values = [f"id-{i}" for i in range(MAX_IN_FILTER_VALUES + 1)]
    with pytest.raises(ValueError, match="at most"):
        parse_filter({"in": {"property": ["node", "externalId"], "values": values}})


def test_parse_filter_allows_max_in_values() -> None:
    values = [f"id-{i}" for i in range(MAX_IN_FILTER_VALUES)]
    parsed = parse_filter({"in": {"property": ["node", "externalId"], "values": values}})
    assert parsed is not None
    assert len(parsed["in"]["values"]) == MAX_IN_FILTER_VALUES


def test_parse_filter_validates_nested_in() -> None:
    values = [f"id-{i}" for i in range(MAX_IN_FILTER_VALUES + 1)]
    with pytest.raises(ValueError, match=r"filter\.and\[0\]\.in"):
        parse_filter(
            {
                "and": [
                    {"in": {"property": ["node", "externalId"], "values": values}},
                ]
            }
        )


def test_get_filter_docs_includes_limits_and_search_guidance() -> None:
    docs = json.loads(get_filter_docs())
    assert docs["limits"]["inFilterMaxValues"] == MAX_IN_FILTER_VALUES
    assert docs["limits"]["applyDeleteMaxItemsPerCall"] == MAX_INSTANCE_WRITE_BATCH
    assert "searchThenQuery" in docs["searchVsQuery"]
    assert "operator=AND" in docs["searchVsQuery"]["search_instances"]
    assert "docs.cognite.com" in docs["docs"]["searchFeatures"]
    assert "dm_limits_and_restrictions" in docs["docs"]["limitsAndRestrictions"]


def test_server_exposes_search_operator_and_query_properties() -> None:
    from cognite_cdf_mcp.server import mcp

    tools = {t.name: t for t in mcp._tool_manager.list_tools()}
    assert "operator" in tools["search_instances"].parameters["properties"]
    assert "properties" in tools["query_instances"].parameters["properties"]
