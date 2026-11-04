"""Process-local session state: which environment tools target by default."""

from __future__ import annotations

import threading

from cognite_cdf_mcp.config import DEFAULT_ENVIRONMENT, normalize_environment_name

_lock = threading.Lock()
_active_environment: str = DEFAULT_ENVIRONMENT


def get_active_environment() -> str:
    """Current session environment alias (starts as ``default``)."""
    with _lock:
        return _active_environment


def set_active_environment(name: str | None) -> str:
    """Set the session environment (normalized). Caller validates the alias exists."""
    global _active_environment
    normalized = normalize_environment_name(name)
    with _lock:
        _active_environment = normalized
    return normalized
