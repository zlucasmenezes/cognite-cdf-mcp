"""Credential providers for CogniteClient."""

from cognite.client.credentials import CredentialProvider, Token

from cognite_cdf_mcp.config import ResolvedSettings, Settings


def create_credentials(settings: Settings | ResolvedSettings) -> CredentialProvider:
    """Build a bearer-token credential provider (``CDF_TOKEN``).

    Interactive / device-code can be added here later without changing tools.
    """
    token = settings.cdf_token.strip()
    if not token:
        raise ValueError("CDF_TOKEN is required")
    return Token(token)
