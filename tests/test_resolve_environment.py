"""Unit tests for multi-environment config resolution (no CDF network)."""

from __future__ import annotations

import pytest

from cognite_cdf_mcp.config import (
    DEFAULT_ENVIRONMENT,
    Settings,
    UnknownEnvironmentError,
    available_environments,
    discover_environments,
    normalize_environment_name,
    resolve_environment,
)


def _base(**overrides: str) -> Settings:
    values = {
        "cdf_project": "proj-default",
        "cdf_cluster": "cluster-a",
        "cdf_token": "token-default",
    }
    values.update(overrides)
    return Settings(**values)


def test_normalize_environment_name() -> None:
    assert normalize_environment_name(None) == DEFAULT_ENVIRONMENT
    assert normalize_environment_name("") == DEFAULT_ENVIRONMENT
    assert normalize_environment_name("  QA ") == "qa"


def test_discover_environments_ignores_bare_project_and_reserved_default() -> None:
    environ = {
        "CDF_PROJECT": "proj-default",
        "CDF_PROJECT_DEFAULT": "should-ignore",
        "CDF_PROJECT_QA": "proj-qa",
        "CDF_PROJECT_DEV": "proj-dev",
        "CDF_CLUSTER_QA": "cluster-qa",
        "CDF_TOKEN_DEV": "token-dev",
        "CDF_TOKEN": "token-default",
    }
    found = discover_environments(environ)
    assert set(found) == {"qa", "dev"}
    assert found["qa"].project == "proj-qa"
    assert found["qa"].cluster == "cluster-qa"
    assert found["qa"].token is None
    assert found["dev"].token == "token-dev"
    assert found["dev"].cluster is None


def test_available_environments_lists_default_first() -> None:
    environ = {"CDF_PROJECT_PROD": "proj-prod", "CDF_PROJECT_QA": "proj-qa"}
    assert available_environments(environ) == ["default", "prod", "qa"]


def test_resolve_default_uses_base_profile() -> None:
    cfg = resolve_environment(None, base=_base())
    assert cfg.environment == "default"
    assert cfg.cdf_project == "proj-default"
    assert cfg.cdf_cluster == "cluster-a"
    assert cfg.cdf_token == "token-default"
    assert cfg.base_url == "https://cluster-a.cognitedata.com"
    assert cfg.client_cache_key == ("proj-default", "cluster-a", "token-default")


def test_resolve_alias_inherits_cluster_and_token() -> None:
    environ = {"CDF_PROJECT_QA": "proj-qa"}
    cfg = resolve_environment("qa", base=_base(), environ=environ)
    assert cfg.environment == "qa"
    assert cfg.cdf_project == "proj-qa"
    assert cfg.cdf_cluster == "cluster-a"
    assert cfg.cdf_token == "token-default"


def test_resolve_alias_overrides_cluster_and_token() -> None:
    environ = {
        "CDF_PROJECT_PROD": "proj-prod",
        "CDF_CLUSTER_PROD": "cluster-prod",
        "CDF_TOKEN_PROD": "token-prod",
    }
    cfg = resolve_environment("PROD", base=_base(), environ=environ)
    assert cfg.environment == "prod"
    assert cfg.cdf_project == "proj-prod"
    assert cfg.cdf_cluster == "cluster-prod"
    assert cfg.cdf_token == "token-prod"


def test_resolve_unknown_alias_raises() -> None:
    with pytest.raises(UnknownEnvironmentError) as exc_info:
        resolve_environment("staging", base=_base(), environ={"CDF_PROJECT_QA": "proj-qa"})
    assert exc_info.value.name == "staging"
    assert "default" in exc_info.value.available
    assert "qa" in exc_info.value.available
