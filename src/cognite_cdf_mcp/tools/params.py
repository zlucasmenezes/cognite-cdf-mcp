"""Normalize MCP tool inputs from hosts/inspectors."""


def optional_str(value: str | None) -> str | None:
    """Treat blank strings as missing (MCP hosts often send ``\"\"``)."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
