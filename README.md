# cognite-cdf-mcp

[Model Context Protocol](https://modelcontextprotocol.io/) server for [Cognite Data Fusion](https://docs.cognite.com/).

### Schema reads (`dataModelsAcl:READ`)

| Tool | Description |
| --- | --- |
| `list_data_models` | List data models (lean metadata + view refs; default `limit=100`) |
| `get_data_model` | Retrieve one data model by space / externalId / version |
| `list_spaces` | List spaces (default `limit=100`) |
| `get_space` | Retrieve one space by id |
| `list_views` | List views (lean metadata, no full property dump; default `limit=100`) |
| `get_view` | Retrieve one view by space / externalId / version |
| `list_containers` | List containers (lean metadata; default `limit=100`) |
| `get_container` | Retrieve one container by space / externalId |
| `get_filter_docs` | Filter DSL examples and property-path tips for instance queries |

### Instance reads (`dataModelInstancesAcl:READ`)

| Tool | Description |
| --- | --- |
| `get_instance` | Retrieve one node/edge by space / externalId (optional view projection) |
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
- Access to a CDF project via **client credentials** or a short-lived **bearer token**

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
| `CDF_LOGIN_FLOW` | `client_credentials` (default) or `token` |

**`client_credentials`:**

| Variable | Description |
| --- | --- |
| `IDP_TENANT_ID` | Microsoft Entra ID tenant |
| `IDP_CLIENT_ID` | OAuth client id |
| `IDP_CLIENT_SECRET` | OAuth client secret |

**`token`:**

| Variable | Description |
| --- | --- |
| `CDF_TOKEN` | Bearer access token for CDF |

Example for token auth:

```bash
CDF_LOGIN_FLOW=token
CDF_PROJECT=your-project
CDF_CLUSTER=westeurope-1
CDF_TOKEN=eyJ...
```

## Run locally

```bash
uv run cognite-cdf-mcp
# or
uv run python -m cognite_cdf_mcp
```

Logs go to **stderr** (stdout is reserved for MCP JSON-RPC).

## Cursor MCP config

### Client credentials

```json
{
  "mcpServers": {
    "cognite-cdf": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/cognite-cdf-mcp", "run", "cognite-cdf-mcp"],
      "env": {
        "CDF_LOGIN_FLOW": "client_credentials",
        "CDF_PROJECT": "your-project",
        "CDF_CLUSTER": "westeurope-1",
        "IDP_TENANT_ID": "00000000-0000-0000-0000-000000000000",
        "IDP_CLIENT_ID": "your-client-id",
        "IDP_CLIENT_SECRET": "your-client-secret"
      }
    }
  }
}
```

### Token

```json
{
  "mcpServers": {
    "cognite-cdf": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/cognite-cdf-mcp", "run", "cognite-cdf-mcp"],
      "env": {
        "CDF_LOGIN_FLOW": "token",
        "CDF_PROJECT": "your-project",
        "CDF_CLUSTER": "westeurope-1",
        "CDF_TOKEN": "eyJ..."
      }
    }
  }
}
```

You can omit `env` if the process inherits a loaded `.env` via your shell, but putting secrets in MCP `env` is clearer for Cursor.

## Lint / format

```bash
uv run ruff check .
uv run ruff format .
```

## Smoke test (MCP Inspector)

```bash
uv run mcp dev src/cognite_cdf_mcp/server.py
```

Open the Inspector URL, connect, and call the list/get tools for spaces, data models, and views.

## Project layout

```
src/cognite_cdf_mcp/
  server.py              # MCPServer + tool registration
  config.py              # pydantic-settings
  cdf/auth.py            # credential providers
  cdf/client.py          # CogniteClient factory
  tools/                 # list/get/delete tool implementations
    params.py            # shared input helpers
```

Auth is isolated behind `create_credentials()` / `create_cognite_client()` so interactive login can be added later without changing the tools.
