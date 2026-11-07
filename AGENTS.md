# Agent guide: using cognite-cdf-mcp

This server is an experimental [Model Context Protocol](https://modelcontextprotocol.io/) interface to [Cognite Data Fusion](https://docs.cognite.com/) Data Modeling. It is not an official Cognite product. APIs and tools may change. Use it to read and write CDF data; call `get_filter_docs` before you write a filter.

## Auth and environments

Auth is a short-lived bearer token. The built-in `default` environment is `CDF_PROJECT`, `CDF_CLUSTER`, and `CDF_TOKEN`. The process starts on `default`.

Additional environments are `CDF_PROJECT_<ALIAS>` (alias lowercased). `CDF_CLUSTER_<ALIAS>` and `CDF_TOKEN_<ALIAS>` are optional and fall back to the base values. Do not commit tokens; keep them in local `.env` or the MCP `env` block. Tools never return tokens.

- `list_environments` lists `default` and every alias (project, cluster, active flag).
- `use_environment(name="qa")` sets the session default for following calls.
- Any CDF tool accepts `environment` to override that default for one call. JSON object responses include `environment` and `project`.
- An unknown alias returns `UnknownEnvironment` and the available names.

Pagination cursors are project-scoped. After you switch project, run the query again. Do not reuse `nextCursor` from another project.

## Writes

Write tools (`apply_*` / `delete_*`) default to `dry_run=true` (preview only). Pass `dry_run=false` only when you intend to mutate CDF. Read `environment` and `project` on the preview before a real write. Schema dry-runs (`apply_spaces`, `delete_spaces`, `delete_view`) only need `READ`.

`apply_instances` writes one sequence: all nodes first, then all edges. Each CDF call sends at most 1000 nodes and edges combined ([Instances](https://docs.cognite.com/api-reference/concepts/20230101/instances)). Calls run one after another. If a later batch fails, earlier batches may already be written; the error JSON includes `completedBatches` and the space/externalId values already applied.

`delete_instances` chunks ids to at most 1000 per call. If a later batch fails, the error includes `completedBatches` and the ids already deleted.

## Search vs query

`search_instances` is full-text matching on text properties (`operator` defaults to `AND`). It does not return `nextCursor`.

- `operator=AND` — every term must match. Use it for a specific lookup.
- `operator=OR` — any term may match. Use it for exploratory or typeahead search.

Add `filter` on search when you also need exact constraints (status, space, enums).

`query_instances` is exact-match filtering (`equals`, `in`, `range`, `prefix`, `exists`, `hasData`, nested `and` / `or` / `not`) with `cursor` pagination. Prefer it for deterministic reads and for hydrating candidates. Pass `properties=[…]` instead of `"*"` when you only need a few fields. When more rows exist, the response includes `nextCursor`.

`aggregate_instances` returns aggregates for the view. It does not return `nextCursor`.

Search-then-query: `search_instances` to rank candidate anchors, then `query_instances` with an `in` filter on those `externalId` values.

`query_instances` already applies `hasData` for the selected view, and applies `instance_space` as a space equals filter when you pass it. Prefer `instance_space` over a hand-written `["node", "space"]` equals.

## Limits

- Default `limit` is 100 on list, search, query, and aggregate tools. Only `query_instances` and the schema `list_*` tools (`list_spaces`, `list_views`, `list_data_models`, `list_containers`) return `nextCursor`. When they do, call again with `cursor` set to that value until `nextCursor` is null. Do not paginate `search_instances` or `aggregate_instances`. Exceeding CDF concurrency budgets returns 429 ([Limits and restrictions](https://docs.cognite.com/cdf/dm/dm_reference/dm_limits_and_restrictions)).
- `in.values` accepts at most 1000 entries. A larger `in` filter is rejected. This server does not split `in` filters for you. Batch values yourself (≤1000), query each batch, and merge. Dedupe by space + externalId.
- Instance apply sends nodes then edges, at most 1000 combined items per CDF call. That chunking does not apply to `in` filters.

Search operators: [Search features](https://docs.cognite.com/cdf/dm/dm_concepts/dm_search). Filters, pagination, and graph concepts: [Query features](https://docs.cognite.com/cdf/dm/dm_concepts/dm_querying).

## Filters

Call `get_filter_docs` before writing a filter. Pass `filter` as a JSON object or a JSON string. Property paths are arrays:

- Instance: `["node", "externalId"]` (also `edge`, and `space`, `createdTime`, `lastUpdatedTime`, `version`, `type`).
- View property: `["viewSpace", "ViewExternalId/version", "propertyId"]`. Include the view version, for example `["cdf_cdm", "CogniteAsset/v1", "name"]`.
- Container property: `["containerSpace", "containerExternalId", "propertyId"]`.

In relation filters, prefer `[space, "ViewExternalId/version", property]`.

`aggregate_instances` property names are strings relative to the view, for example `{"count": {"property": "externalId"}}`.

## Graph steps

There is no graph traversal tool. Walk a relation with successive `query_instances` calls.

A step that filters `["edge", "type"]` must pass `instance_type="edge"`. Read the edge, then follow `startNode` and `endNode` with both `space` and `externalId` still attached. Hydrate those nodes with `query_instances` (`instance_type="node"`) and an `in` filter on `externalId` in batches of at most 1000. Pass `instance_space` when every id shares one space; when they do not, keep each node's space in the filter. When the first step is discovery, search first, then run a constrained query. Do not scan a view broadly to find a name.

## Typical reads

1. `list_views` (optionally by space) and pick the view, often `CogniteAsset` in `cdf_cdm`.
2. `search_instances` or `query_instances` on that view.
3. `inspect_instance` (`space` + `externalId`) when you need involved views or containers, then `get_instance` with `view_space`, `view_external_id`, and `view_version`.
4. Across projects, pass `environment` per call or `use_environment`, and do not reuse cursors.
