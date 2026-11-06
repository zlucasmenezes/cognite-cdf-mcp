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

`apply_instances` and `delete_instances` auto-chunk to at most 1000 items per CDF call ([Instances](https://docs.cognite.com/api-reference/concepts/20230101/instances)).

## Search vs query

`search_instances` is full-text matching on text properties (`operator` defaults to `AND`):

- `operator=AND` — every term must match. Use it for a specific lookup.
- `operator=OR` — any term may match. Use it for exploratory or typeahead search.

Add `filter` on search when you also need exact constraints (status, space, enums).

`query_instances` is exact-match filtering (`equals`, `in`, `range`, `prefix`, `exists`, `hasData`, nested `and` / `or` / `not`) with `cursor` pagination. Prefer it for deterministic reads and for hydrating candidates. Pass `properties=[…]` instead of `"*"` when you only need a few fields.

Search-then-query: `search_instances` to rank candidate anchors, then `query_instances` with an `in` filter on those `externalId` values.

`query_instances` already applies `hasData` for the selected view, and applies `instance_space` as a space equals filter when you pass it. Prefer `instance_space` over a hand-written `["node", "space"]` equals.

## Limits

- Default `limit` is 100 on list, search, query, and aggregate tools. If the response includes `nextCursor`, call again with `cursor` set to that value until `nextCursor` is null. Page instead of raising the limit. Exceeding CDF concurrency budgets returns 429 ([Limits and restrictions](https://docs.cognite.com/cdf/dm/dm_reference/dm_limits_and_restrictions)).
- `in.values` accepts at most 1000 entries. A larger `in` filter is rejected. This server does not split `in` filters for you. Batch values yourself (≤1000), query each batch, and merge. Dedupe by space + externalId.
- Instance apply/delete auto-chunk at 1000. That chunking does not apply to `in` filters.

Search operators: [Search features](https://docs.cognite.com/cdf/dm/dm_concepts/dm_search). Filters, pagination, and graph concepts: [Query features](https://docs.cognite.com/cdf/dm/dm_concepts/dm_querying).

## Filters

Call `get_filter_docs` before writing a filter. Pass `filter` as a JSON object or a JSON string. Property paths are arrays:

- Instance: `["node", "externalId"]` (also `edge`, and `space`, `createdTime`, `lastUpdatedTime`, `version`, `type`).
- View property: `["viewSpace", "ViewExternalId/version", "propertyId"]`. Include the view version, for example `["cdf_cdm", "CogniteAsset/v1", "name"]`.
- Container property: `["containerSpace", "containerExternalId", "propertyId"]`.

In relation filters, prefer `[space, "ViewExternalId/version", property]`.

`aggregate_instances` property names are strings relative to the view, for example `{"count": {"property": "externalId"}}`.

## Graph steps

Graph traversal is not a single tool. Walk a relation with successive `query_instances` calls: filter one hop (edge type or relation property; see the edge-type example from `get_filter_docs`), then hydrate the next ids with `in` on `externalId` in batches of at most 1000. When the first step is discovery, search first, then run a constrained query. Do not scan a view broadly to find a name.

## Typical reads

1. `list_views` (optionally by space) and pick the view, often `CogniteAsset` in `cdf_cdm`.
2. `search_instances` or `query_instances` on that view.
3. `inspect_instance` (`space` + `externalId`) when you need involved views or containers, then `get_instance` with `view_space`, `view_external_id`, and `view_version`.
4. Across projects, pass `environment` per call or `use_environment`, and do not reuse cursors.
