"""Tool: document CDF instance filter DSL for agents."""

from __future__ import annotations

import json

FILTER_DOCS: dict = {
    "overview": (
        "CDF instance filters are JSON objects passed to query_instances, "
        "search_instances, and aggregate_instances. Property paths are arrays."
    ),
    "propertyPaths": {
        "instance": ["node|edge", "space|externalId|createdTime|lastUpdatedTime|version|type"],
        "viewProperty": ["viewSpace", "viewExternalId/version", "propertyId"],
        "viewPropertyExample": ["cdf_cdm", "CogniteAsset/v1", "name"],
        "containerProperty": ["containerSpace", "containerExternalId", "propertyId"],
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
            "name": "in externalIds",
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
    ],
    "tips": [
        "query_instances already applies hasData for the selected view.",
        "Prefer instance_space on query/search tools instead of hand-writing node.space equals.",
        "For free-text name/alias search, use search_instances instead of filters.",
        "Pass filter as a JSON object (or JSON string). Default result limit is 100.",
        "Use cursor from query_instances responses to page through large result sets.",
        "aggregate_instances properties are strings relative to the view, e.g. "
        '{"count": {"property": "externalId"}} or {"count": {"property": "name"}}.',
    ],
}


def get_filter_docs() -> str:
    """Return static documentation for writing CDF instance filters."""
    return json.dumps(FILTER_DOCS, indent=2)
