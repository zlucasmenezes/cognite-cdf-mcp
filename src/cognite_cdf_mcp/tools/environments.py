"""Tools: list configured CDF environments and switch the session default."""

from __future__ import annotations

import json
from typing import Any

from cognite_cdf_mcp.cdf.session import get_active_environment, set_active_environment
from cognite_cdf_mcp.config import (
    ResolvedSettings,
    UnknownEnvironmentError,
    available_environments,
    normalize_environment_name,
    resolve_environment,
)


def _describe(cfg: ResolvedSettings, *, active: str) -> dict[str, Any]:
    """Describe an environment; never includes token / secret values."""
    return {
        "name": cfg.environment,
        "project": cfg.cdf_project,
        "cluster": cfg.cdf_cluster,
        "active": cfg.environment == active,
    }


def unknown_environment_error(exc: UnknownEnvironmentError) -> dict[str, Any]:
    return {
        "error": "UnknownEnvironment",
        "message": str(exc),
        "available": exc.available,
        "hints": ["Call list_environments to see configured aliases."],
    }


def list_environments() -> str:
    """List ``default`` plus every ``CDF_PROJECT_<ALIAS>`` environment."""
    active = get_active_environment()
    items: list[dict[str, Any]] = []
    for name in available_environments():
        try:
            items.append(_describe(resolve_environment(name), active=active))
        except ValueError as exc:
            items.append({"name": name, "active": name == active, "error": str(exc)})
    return json.dumps({"active": active, "items": items}, indent=2)


def use_environment(name: str) -> str:
    """Set the session default environment (validated; no CDF call)."""
    alias = normalize_environment_name(name)
    try:
        cfg = resolve_environment(alias)
    except UnknownEnvironmentError as exc:
        return json.dumps(unknown_environment_error(exc), indent=2)
    except ValueError as exc:
        return json.dumps({"error": "InvalidEnvironment", "message": str(exc)}, indent=2)

    previous = get_active_environment()
    set_active_environment(alias)
    return json.dumps(
        {
            "previous": previous,
            "active": _describe(cfg, active=alias),
            "note": (
                "Pagination cursors are project-scoped; re-run list/query calls "
                "after switching instead of reusing a previous nextCursor."
                if previous != alias
                else None
            ),
        },
        indent=2,
    )
