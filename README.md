# cognite-cdf-mcp

[Model Context Protocol](https://modelcontextprotocol.io/) server for [Cognite Data Fusion](https://docs.cognite.com/).

> **Status: early development / experimental.** APIs, tools, and config may change without notice. Not an official Cognite product. Use at your own risk — especially write tools (`apply_*` / `delete_*`). Prefer `dry_run=true` until you trust the behavior. Do not commit secrets (`CDF_TOKEN`); keep them in local `.env` or Cursor MCP `env`.

### Environments (no CDF call)

| Tool | Description |
| --- | --- |
| `list_environments` | List `default` + every `CDF_PROJECT_<ALIAS>` environment (project/cluster, active flag; tokens never shown) |
| `use_environment` | Set the session default environment (`default`, `dev`, `qa`, …) |

Every CDF tool below also accepts an optional `environment` argument that overrides the session default for that call. Responses that are JSON objects include `environment` and `project`.

### Schema reads (`dataModelsAcl:READ`)

| Tool | Description |
| --- | --- |
| `list_data_models` | List data models (lean metadata + view refs; `limit=100`, `cursor` / `nextCursor`) |
| `get_data_model` | Retrieve one data model by space / externalId / version |
| `list_spaces` | List spaces (`limit=100`, `cursor` / `nextCursor`) |
| `get_space` | Retrieve one space by id |
| `list_views` | List views (lean metadata; `limit=100`, `cursor` / `nextCursor`) |
| `get_view` | Retrieve one view by space / externalId / version |
| `list_containers` | List containers (lean metadata; `limit=100`, `cursor` / `nextCursor`) |
| `get_container` | Retrieve one container by space / externalId |
| `get_filter_docs` | Filter DSL examples and property-path tips for instance queries |

### Instance reads (`dataModelInstancesAcl:READ`)

| Tool | Description |
| --- | --- |
| `get_instance` | Retrieve one node/edge by space / externalId (optional view projection) |
| `inspect_instance` | List involved views/containers for one node/edge |
| `query_instances` | Query instances through a view (`filter`, `instance_space`, `cursor`; default `limit=100`) |
| `search_instances` | Full-text search through a view (default `limit=100`) |
| `aggregate_instances` | Count/sum/avg/min/max through a view |

### Instance writes (`dataModelInstancesAcl:WRITE`)

| Tool | Description |
| --- | --- |
| `apply_instances` | Create/update nodes/edges (`dry_run` supported; dry run only needs `READ`) |
| `delete_instances` | Delete nodes/edges by ids (`dry_run` supported; dry run only needs `READ`) |

### Schema writes (`dataModelsAcl:WRITE`)

| Tool | Description |
| --- | --- |
| `apply_spaces` | Create/update spaces (`dry_run` supported; dry run only needs `READ`) |
| `delete_spaces` | Delete spaces by id (`dry_run` supported; dry run only needs `READ`) |
| `delete_view` | Delete one view by space / externalId / version (`dry_run` supported; dry run only needs `READ`) |

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Access to a CDF project via a short-lived **bearer token** (`CDF_TOKEN`)

## Setup

```bash
cp .env.example .env
# edit .env with your CDF / auth values

uv sync --group dev
```

### Environment variables

Always required:

| Variable | Description |
| --- | --- |
| `CDF_PROJECT` | CDF project name |
| `CDF_CLUSTER` | Cluster id, e.g. `westeurope-1` |
| `CDF_TOKEN` | Bearer access token for CDF |

Example:

```bash
CDF_PROJECT=your-project
CDF_CLUSTER=westeurope-1
CDF_TOKEN=eyJ...
```

### Multiple environments (dev / qa / prod)

The base `CDF_PROJECT` / `CDF_CLUSTER` / `CDF_TOKEN` is the built-in **`default`** environment. The process starts on `default`; there is no `CDF_DEFAULT_ENVIRONMENT`.

Add more with flat variables. An alias exists iff `CDF_PROJECT_<ALIAS>` is set and non-empty (the suffix is case-insensitive and normalized to lowercase; `default` is reserved):

| Variable | Description |
| --- | --- |
| `CDF_PROJECT_<ALIAS>` | Project for that alias (required to define it) |
| `CDF_CLUSTER_<ALIAS>` | Optional; falls back to `CDF_CLUSTER` |
| `CDF_TOKEN_<ALIAS>` | Optional; falls back to `CDF_TOKEN` |

Aliases are also read from `.env`; real process env vars win.

```bash
CDF_PROJECT=your-dev-project
CDF_CLUSTER=westeurope-1
CDF_TOKEN=eyJ...

CDF_PROJECT_DEV=your-dev-project
CDF_PROJECT_QA=your-qa-project
CDF_PROJECT_PROD=your-prod-project
# CDF_CLUSTER_PROD=other-cluster
# CDF_TOKEN_PROD=eyJ-only-if-different
```

Selecting an environment:

- `use_environment(name="qa")` sets the session default for all following tool calls.
- Any tool call can pass `environment="prod"` to override once, without changing the session default.
- Unknown aliases return a JSON `UnknownEnvironment` error listing the available names.
- Pagination cursors are project-scoped: re-query after switching instead of reusing `nextCursor`.

## Run locally

```bash
uv run cognite-cdf-mcp
# or
uv run python -m cognite_cdf_mcp
```

Logs go to **stderr** (stdout is reserved for MCP JSON-RPC).

## Cursor MCP config

### Single project

```json
{
  "mcpServers": {
    "cognite-cdf": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/cognite-cdf-mcp", "run", "cognite-cdf-mcp"],
      "env": {
        "CDF_PROJECT": "your-project",
        "CDF_CLUSTER": "westeurope-1",
        "CDF_TOKEN": "eyJ..."
      }
    }
  }
}
```

### Multiple environments

One token shared by all projects (add `CDF_TOKEN_<ALIAS>` only where it differs):

```json
{
  "mcpServers": {
    "cognite-cdf": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/cognite-cdf-mcp", "run", "cognite-cdf-mcp"],
      "env": {
        "CDF_PROJECT": "your-dev-project",
        "CDF_CLUSTER": "westeurope-1",
        "CDF_TOKEN": "eyJ...",
        "CDF_PROJECT_DEV": "your-dev-project",
        "CDF_PROJECT_QA": "your-qa-project",
        "CDF_PROJECT_PROD": "your-prod-project"
      }
    }
  }
}
```

You can omit `env` if the process inherits a loaded `.env` via your shell, but putting secrets in MCP `env` is clearer for Cursor.

### Run from GitHub with `uvx` (no local clone)

```json
{
  "mcpServers": {
    "cognite-cdf": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/zlucasmenezes/cognite-cdf-mcp.git",
        "cognite-cdf-mcp"
      ],
      "env": {
        "CDF_PROJECT": "your-project",
        "CDF_CLUSTER": "westeurope-1",
        "CDF_TOKEN": "eyJ..."
      }
    }
  }
}
```

Pin a version with `@v0.1.0` (or another tag) on the git URL when you publish releases.

## Lint / format / test

```bash
uv sync --group dev
uv run ruff check --fix .
uv run ruff format .
uv run pytest -q
```

CI (GitHub Actions on `main` / PRs) runs ruff check + format `--check`, imports the MCP server, and pytest.

### Pre-commit

Runs `ruff check --fix` and `ruff format` automatically on every commit:

```bash
uv sync --group dev
uv run pre-commit install
```

Run against all files once:

```bash
uv run pre-commit run --all-files
```

## Smoke test (MCP Inspector)

```bash
uv run mcp dev src/cognite_cdf_mcp/server.py
```

Open the Inspector URL, connect, and call the list/get tools for spaces, data models, and views.

## Recipes

### Find an asset by name or alias

1. `list_views` (optionally filter by space) → pick the asset view (often `CogniteAsset` in `cdf_cdm`).
2. `search_instances` with `query="AFA10"` and `properties=["name","aliases"]` on that view.
3. If needed, `get_instance` with the returned `space` / `externalId` and the same view projection.

### Page through a large space listing

1. `list_spaces` (or `list_views` / `query_instances`) with `limit=100`.
2. If the response includes `nextCursor`, call again with `cursor=<that value>` until `nextCursor` is null.

### Discover which view to use for an instance

1. `inspect_instance` with `space` + `externalId`.
2. Read `inspectionResults.involvedViews` / `involvedContainers`.
3. `get_instance` again with `view_space` / `view_external_id` / `view_version` from the inspect result.

### Count instances in a view (optionally filtered)

1. `get_filter_docs` if you need filter syntax.
2. `aggregate_instances` with e.g. `aggregates={"count":{"property":"externalId"}}`, plus `instance_space` and/or `filter`.

### Compare / act across QA and prod

1. `list_environments` to confirm the aliases (`qa`, `prod`) and their projects.
2. Read from each without switching: `list_views(space="my_space", environment="qa")`, then the same call with `environment="prod"`; compare the results.
3. Or `use_environment(name="qa")`, work there, then `use_environment(name="prod")` (or `default`).
4. For writes, run `dry_run=true` with an explicit `environment="prod"` first, check the `environment` / `project` fields in the response, then repeat with `dry_run=false` only when intentional.

### Safe dry-run before writing

1. Prefer `dry_run=true` on `apply_instances`, `delete_instances`, `apply_spaces`, `delete_spaces`, or `delete_view`.
2. Review the JSON preview, then call again with `dry_run=false` only when intentional.

## Project layout

```
src/cognite_cdf_mcp/
  server.py              # MCPServer + tool registration
  config.py              # pydantic-settings + CDF_PROJECT_<ALIAS> discovery / resolve_environment
  cdf/auth.py            # credential providers
  cdf/client.py          # CogniteClient factory + per-project client cache
  cdf/session.py         # active (session) environment
  tools/environments.py  # list_environments / use_environment
  tools/                 # list/get/delete tool implementations
    params.py            # shared input helpers
    schema_page.py       # cursor pagination for schema lists
    errors.py            # actionable NotFound helpers
```

Auth is isolated behind `create_credentials()` / `create_cognite_client()` so interactive login can be added later without changing the tools.
