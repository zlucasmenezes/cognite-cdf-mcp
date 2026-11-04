"""Credential providers for CogniteClient."""

from cognite.client.credentials import (
    CredentialProvider,
    OAuthClientCredentials,
    Token,
)

from cognite_cdf_mcp.config import ResolvedSettings, Settings


def create_credentials(settings: Settings | ResolvedSettings) -> CredentialProvider:
    """Build a credential provider based on ``CDF_LOGIN_FLOW``.

    Supported:
    - ``client_credentials`` — Entra ID client id/secret
    - ``token`` — static bearer token (``CDF_TOKEN``)

    Interactive / device-code can be added here later without changing tools.
    """
    if settings.cdf_login_flow == "client_credentials":
        assert settings.idp_client_id is not None
        assert settings.idp_client_secret is not None
        return OAuthClientCredentials(
            token_url=settings.token_url,
            client_id=settings.idp_client_id,
            client_secret=settings.idp_client_secret,
            scopes=settings.scopes,
        )

    if settings.cdf_login_flow == "token":
        assert settings.cdf_token is not None
        return Token(settings.cdf_token)

    raise ValueError(
        f"Unsupported CDF_LOGIN_FLOW={settings.cdf_login_flow!r}. "
        "Supported: client_credentials, token"
    )
