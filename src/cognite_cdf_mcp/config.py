"""Typed configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LoginFlow = Literal["client_credentials", "token"]


class Settings(BaseSettings):
    """CDF and IdP settings for the MCP server."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    cdf_project: str = Field(..., description="CDF project name")
    cdf_cluster: str = Field(..., description="CDF cluster, e.g. westeurope-1")
    cdf_login_flow: LoginFlow = Field(
        default="client_credentials",
        description="Auth flow: client_credentials or token",
    )

    # client_credentials
    idp_tenant_id: str | None = Field(default=None, description="Microsoft Entra ID tenant ID")
    idp_client_id: str | None = Field(default=None, description="OAuth client ID")
    idp_client_secret: str | None = Field(default=None, description="OAuth client secret")

    # token
    cdf_token: str | None = Field(default=None, description="Bearer access token for CDF")

    @model_validator(mode="after")
    def validate_auth_fields(self) -> Self:
        if self.cdf_login_flow == "client_credentials":
            missing = [
                name
                for name, value in (
                    ("IDP_TENANT_ID", self.idp_tenant_id),
                    ("IDP_CLIENT_ID", self.idp_client_id),
                    ("IDP_CLIENT_SECRET", self.idp_client_secret),
                )
                if not value
            ]
            if missing:
                raise ValueError("client_credentials flow requires: " + ", ".join(missing))
        elif self.cdf_login_flow == "token":
            if not self.cdf_token:
                raise ValueError("token flow requires: CDF_TOKEN")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def base_url(self) -> str:
        return f"https://{self.cdf_cluster}.cognitedata.com"

    @property
    def token_url(self) -> str:
        if not self.idp_tenant_id:
            raise ValueError("IDP_TENANT_ID is required to build token_url")
        return f"https://login.microsoftonline.com/{self.idp_tenant_id}/oauth2/v2.0/token"

    @property
    def scopes(self) -> list[str]:
        return [f"{self.base_url}/.default"]


@lru_cache
def get_settings() -> Settings:
    """Load settings once; fails early if required env vars are missing."""
    return Settings()  # type: ignore[call-arg]
