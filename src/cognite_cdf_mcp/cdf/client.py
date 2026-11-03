"""Factory for an authenticated CogniteClient."""

from functools import lru_cache

from cognite.client import ClientConfig, CogniteClient

from cognite_cdf_mcp.cdf.auth import create_credentials
from cognite_cdf_mcp.config import Settings, get_settings


def create_cognite_client(settings: Settings | None = None) -> CogniteClient:
    """Create a CogniteClient using the configured auth flow."""
    cfg = settings or get_settings()
    credentials = create_credentials(cfg)
    return CogniteClient(
        ClientConfig(
            client_name="cognite-cdf-mcp",
            project=cfg.cdf_project,
            credentials=credentials,
            base_url=cfg.base_url,
        )
    )


@lru_cache
def get_cognite_client() -> CogniteClient:
    """Cached client for the lifetime of the MCP process."""
    return create_cognite_client()
