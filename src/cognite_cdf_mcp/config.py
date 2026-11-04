"""Typed configuration loaded from environment variables."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, Self

from dotenv import dotenv_values
from pydantic import Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

LoginFlow = Literal["client_credentials", "token"]

DEFAULT_ENVIRONMENT = "default"
PROJECT_ALIAS_PREFIX = "CDF_PROJECT_"
CLUSTER_ALIAS_PREFIX = "CDF_CLUSTER_"
TOKEN_ALIAS_PREFIX = "CDF_TOKEN_"

_warned_reserved: set[str] = set()


class UnknownEnvironmentError(ValueError):
    """Raised when an environment alias is not configured."""

    def __init__(self, name: str, available: list[str]) -> None:
        self.name = name
        self.available = available
        super().__init__(
            f"Unknown environment {name!r}. Available: {', '.join(available)}. "
            "Call list_environments to see configured aliases."
        )


class Settings(BaseSettings):
    """CDF and IdP settings for the MCP server (the ``default`` profile)."""

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


@dataclass(frozen=True)
class EnvironmentOverrides:
    """Alias-specific values discovered from flat ``CDF_*_<ALIAS>`` variables."""

    alias: str
    project: str
    cluster: str | None = None
    token: str | None = None


@dataclass(frozen=True)
class ResolvedSettings:
    """Fully merged settings for one environment (alias over defaults).

    Exposes the same attribute names as :class:`Settings` so credential
    providers can use either.
    """

    environment: str
    cdf_project: str
    cdf_cluster: str
    cdf_login_flow: LoginFlow
    idp_tenant_id: str | None = None
    idp_client_id: str | None = None
    idp_client_secret: str | None = None
    cdf_token: str | None = None

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

    @property
    def client_cache_key(self) -> tuple[str, str, str, str]:
        """Identity of the underlying client (project, cluster, flow, credential id)."""
        credential = (
            self.cdf_token or "" if self.cdf_login_flow == "token" else self.idp_client_id or ""
        )
        return (self.cdf_project, self.cdf_cluster, self.cdf_login_flow, credential)


def normalize_environment_name(name: str | None) -> str:
    """Lowercase/trim an alias; empty or ``None`` means ``default``."""
    cleaned = (name or "").strip().lower()
    return cleaned or DEFAULT_ENVIRONMENT


def _environ_snapshot(environ: Mapping[str, str] | None) -> dict[str, str]:
    """Process env, plus ``.env`` values (process env wins) when not injected."""
    if environ is not None:
        return {k.upper(): v for k, v in environ.items()}
    merged: dict[str, str] = {}
    for key, value in dotenv_values(".env").items():
        if value is not None:
            merged[key.upper()] = value
    merged.update({k.upper(): v for k, v in os.environ.items()})
    return merged


def discover_environments(
    environ: Mapping[str, str] | None = None,
) -> dict[str, EnvironmentOverrides]:
    """Scan ``CDF_PROJECT_<ALIAS>`` (plus optional cluster/token) into an alias map.

    Alias names are lowercased. The bare ``CDF_PROJECT`` is the ``default`` profile
    and is not returned here. Pass ``environ`` to avoid reading the real environment.
    """
    env = _environ_snapshot(environ)
    found: dict[str, EnvironmentOverrides] = {}
    for key in sorted(env):
        if not key.startswith(PROJECT_ALIAS_PREFIX):
            continue
        suffix = key[len(PROJECT_ALIAS_PREFIX) :]
        project = env[key].strip()
        if not suffix or not project:
            continue
        alias = suffix.lower()
        if alias == DEFAULT_ENVIRONMENT:
            if key not in _warned_reserved:
                _warned_reserved.add(key)
                logger.warning(
                    "Ignoring %s: 'default' is reserved for the base CDF_PROJECT profile", key
                )
            continue
        cluster = (env.get(CLUSTER_ALIAS_PREFIX + suffix) or "").strip() or None
        token = (env.get(TOKEN_ALIAS_PREFIX + suffix) or "").strip() or None
        found[alias] = EnvironmentOverrides(
            alias=alias, project=project, cluster=cluster, token=token
        )
    return found


def available_environments(
    environ: Mapping[str, str] | None = None,
) -> list[str]:
    """``default`` first, then discovered aliases (sorted)."""
    return [DEFAULT_ENVIRONMENT, *sorted(discover_environments(environ))]


def resolve_environment(
    name: str | None = None,
    *,
    base: Settings | None = None,
    environ: Mapping[str, str] | None = None,
) -> ResolvedSettings:
    """Merge an alias over the base settings.

    ``None``/``"default"`` returns the base ``CDF_PROJECT`` profile. Cluster and
    token fall back to the base values; client_credentials stay global.
    Does not touch the network.
    """
    cfg = base or get_settings()
    alias = normalize_environment_name(name)

    if alias == DEFAULT_ENVIRONMENT:
        return ResolvedSettings(
            environment=DEFAULT_ENVIRONMENT,
            cdf_project=cfg.cdf_project,
            cdf_cluster=cfg.cdf_cluster,
            cdf_login_flow=cfg.cdf_login_flow,
            idp_tenant_id=cfg.idp_tenant_id,
            idp_client_id=cfg.idp_client_id,
            idp_client_secret=cfg.idp_client_secret,
            cdf_token=cfg.cdf_token,
        )

    aliases = discover_environments(environ)
    override = aliases.get(alias)
    if override is None:
        raise UnknownEnvironmentError(alias, [DEFAULT_ENVIRONMENT, *sorted(aliases)])

    token = override.token or cfg.cdf_token
    if cfg.cdf_login_flow == "token" and not token:
        raise ValueError(
            f"Environment {alias!r} needs a token: set CDF_TOKEN_{alias.upper()} or CDF_TOKEN"
        )

    return ResolvedSettings(
        environment=alias,
        cdf_project=override.project,
        cdf_cluster=override.cluster or cfg.cdf_cluster,
        cdf_login_flow=cfg.cdf_login_flow,
        idp_tenant_id=cfg.idp_tenant_id,
        idp_client_id=cfg.idp_client_id,
        idp_client_secret=cfg.idp_client_secret,
        cdf_token=token,
    )
