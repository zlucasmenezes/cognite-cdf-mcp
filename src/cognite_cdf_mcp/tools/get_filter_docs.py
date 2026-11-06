"""Tool: document CDF instance filter DSL for agents."""

from __future__ import annotations

import json

from cognite_cdf_mcp.tools.params import (
    DEFAULT_LIMIT,
    MAX_IN_FILTER_VALUES,
    MAX_INSTANCE_WRITE_BATCH,
)

FILTER_DOCS: dict = {
    "overview": (
        "CDF instance filters are JSON objects passed to query_instances, "
        "search_instances, and aggregate_instances. Property paths are arrays."
    ),
    "docs": {
        "limitsAndRestrictions": (
            "https://docs.cognite.com/cdf/dm/dm_reference/dm_limits_and_restrictions"
        ),
        "instancesApi": ("https://docs.cognite.com/api-reference/concepts/20230101/instances"),
        "searchFeatures": "https://docs.cognite.com/cdf/dm/dm_concepts/dm_search",
        "queryFeatures": "https://docs.cognite.com/cdf/dm/dm_concepts/dm_querying",
    },
    "propertyPaths": {
        "instance": ["node|edge", "space|externalId|createdTime|lastUpdatedTime|version|type"],
        "viewProperty": ["viewSpace", "viewExternalId/version", "propertyId"],
        "viewPropertyExample": ["cdf_cdm", "CogniteAsset/v1", "name"],
        "containerProperty": ["containerSpace", "containerExternalId", "propertyId"],
        "versionedTraversalTip": (
            "In relation / traversal filters prefer "
            "[space, 'ViewExternalId/version', property] — include the view version."
        ),
    },
    "searchVsQuery": {
        "search_instances": (
            "Free-text / fuzzy matching on text properties. Use operator=AND "
            "(default) for a specific lookup; operator=OR for exploratory or "
            "typeahead search. Combine with filter for exact constraints."
        ),
        "query_instances": (
            "Exact-match filtering (equals, in, range, hasData, …) with cursor "
            "pagination. Prefer for deterministic reads and hydrating candidates. "
            "Pass properties=[…] instead of '*' when you only need a few fields."
        ),
        "searchThenQuery": (
            "Discovery pattern: search_instances to rank candidate anchors, then "
            "query_instances with an in filter on those externalIds (batches of "
            f"≤{MAX_IN_FILTER_VALUES}) to hydrate related properties / graph steps."
        ),
        "whenNotToTraverseBroadly": (
            "Avoid broad query scans when the first step is discovery — search "
            "first, then constrained query."
        ),
    },
    "limits": {
        "defaultResultLimit": DEFAULT_LIMIT,
        "inFilterMaxValues": MAX_IN_FILTER_VALUES,
        "applyDeleteMaxItemsPerCall": MAX_INSTANCE_WRITE_BATCH,
        "notes": [
            f"in.values accepts at most {MAX_IN_FILTER_VALUES} entries; "
            "this MCP rejects larger filters early. Split into batches and merge.",
            "apply_instances writes nodes and edges together, nodes first, "
            f"at most {MAX_INSTANCE_WRITE_BATCH} items per CDF call. "
            "delete_instances chunks one id list to at most "
            f"{MAX_INSTANCE_WRITE_BATCH} ids per CDF call.",
            "Only query_instances and schema list_* tools return nextCursor. "
            "search_instances and aggregate_instances do not. Page with "
            "nextCursor instead of raising limits aggressively. Exceeding CDF "
            "concurrency budgets returns 429.",
        ],
    },
    "examples": [
        {
            "name": "equals string property",
            "filter": {
                "equals": {
                    "property": ["cdf_cdm", "CogniteAsset/v1", "name"],
                    "value": "FWL01",
                }
            },
        },
        {
            "name": "in externalIds (≤1000 values)",
            "filter": {
                "in": {
                    "property": ["node", "externalId"],
                    "values": ["MCH-aaa", "MCH-bbb"],
                }
            },
        },
        {
            "name": "prefix on name",
            "filter": {
                "prefix": {
                    "property": ["cdf_cdm", "CogniteAsset/v1", "name"],
                    "value": "FW",
                }
            },
        },
        {
            "name": "exists property",
            "filter": {
                "exists": {
                    "property": ["cdf_cdm", "CogniteAsset/v1", "description"],
                }
            },
        },
        {
            "name": "and / or / not",
            "filter": {
                "and": [
                    {
                        "equals": {
                            "property": ["node", "space"],
                            "value": "sp_ash_fra_dat",
                        }
                    },
                    {
                        "prefix": {
                            "property": ["node", "externalId"],
                            "value": "MCH-",
                        }
                    },
                ]
            },
        },
        {
            "name": "hasData on a view (usually applied automatically when querying a view)",
            "filter": {
                "hasData": [
                    {
                        "type": "view",
                        "space": "cdf_cdm",
                        "externalId": "CogniteAsset",
                        "version": "v1",
                    }
                ]
            },
        },
        {
            "name": "range on lastUpdatedTime",
            "filter": {
                "range": {
                    "property": ["node", "lastUpdatedTime"],
                    "gte": 1700000000000,
                }
            },
        },
        {
            "name": "edge type equals (relationship step)",
            "filter": {
                "equals": {
                    "property": ["edge", "type"],
                    "value": {"space": "my_space", "externalId": "PrimaryToSecondaryLink"},
                }
            },
        },
    ],
    "tips": [
        "query_instances already applies hasData for the selected view and "
        "instance_space as node|edge.space equals when provided.",
        "Prefer instance_space on query/search tools instead of hand-writing node.space equals.",
        "For free-text name/alias search, use search_instances (AND vs OR) instead of filters.",
        "After search, hydrate with query_instances + in on externalId (search-then-query).",
        "Pass filter as a JSON object (or JSON string). Default result limit is 100.",
        "Use nextCursor from query_instances and list_* schema tools to page large result sets.",
        "Select only needed properties on query_instances to shrink payloads before LLM use.",
        "Dedupe by space+externalId when merging batched in-filter or multi-step results.",
        "aggregate_instances properties are strings relative to the view, e.g. "
        '{"count": {"property": "externalId"}} or {"count": {"property": "name"}}.',
    ],
}


def get_filter_docs() -> str:
    """Return static documentation for writing CDF instance filters."""
    return json.dumps(FILTER_DOCS, indent=2)
