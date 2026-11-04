"""Factory and cache for authenticated CogniteClients (one per project/cluster/creds)."""

from __future__ import annotations

import threading

from cognite.client import ClientConfig, CogniteClient

from cognite_cdf_mcp.cdf.auth import create_credentials
from cognite_cdf_mcp.cdf.session import get_active_environment
from cognite_cdf_mcp.config import ResolvedSettings, Settings, resolve_environment

_clients: dict[tuple[str, str, str], CogniteClient] = {}
_clients_lock = threading.Lock()


def create_cognite_client(settings: Settings | ResolvedSettings | None = None) -> CogniteClient:
    """Create a CogniteClient using the configured bearer token (no network calls)."""
    cfg = settings or resolve_environment(None)
    credentials = create_credentials(cfg)
    return CogniteClient(
        ClientConfig(
            client_name="cognite-cdf-mcp",
            project=cfg.cdf_project,
            credentials=credentials,
            base_url=cfg.base_url,
        )
    )


def effective_environment(environment: str | None = None) -> str:
    """Per-call override wins; otherwise the session environment."""
    return environment.strip() if environment and environment.strip() else get_active_environment()


def resolve_active_settings(environment: str | None = None) -> ResolvedSettings:
    """Resolve settings for an explicit ``environment`` or the session default."""
    return resolve_environment(effective_environment(environment))


def get_cognite_client(environment: str | None = None) -> CogniteClient:
    """Cached client for ``environment`` (or the session environment)."""
    cfg = resolve_active_settings(environment)
    key = cfg.client_cache_key
    with _clients_lock:
        client = _clients.get(key)
        if client is None:
            client = create_cognite_client(cfg)
            _clients[key] = client
        return client


def clear_client_cache() -> None:
    """Drop cached clients (mainly for tests)."""
    with _clients_lock:
        _clients.clear()
