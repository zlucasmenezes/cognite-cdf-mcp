"""Shared helpers for instance tools."""

from __future__ import annotations

from typing import Any, Literal

from cognite.client.data_classes.data_modeling import ViewId
from cognite.client.data_classes.filters import And, Equals, Filter, HasData

from cognite_cdf_mcp.tools.params import optional_str

InstanceType = Literal["node", "edge"]


def view_id(
    *,
    view_space: str,
    view_external_id: str,
    view_version: str,
) -> ViewId:
    return ViewId(
        space=view_space,
        external_id=view_external_id,
        version=view_version,
    )


def optional_view_id(
    *,
    view_space: str | None,
    view_external_id: str | None,
    view_version: str | None,
) -> ViewId | None:
    space = optional_str(view_space)
    external_id = optional_str(view_external_id)
    version = optional_str(view_version)
    parts = (space, external_id, version)
    if all(p is None for p in parts):
        return None
    if any(p is None for p in parts):
        raise ValueError("view_space, view_external_id, and view_version must all be set together")
    return ViewId(space=space, external_id=external_id, version=version)  # type: ignore[arg-type]


def as_instance_list(value: Any) -> list[Any]:
    """Normalize a retrieve result to a list (None, one instance, or many)."""
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    space = getattr(value, "space", None)
    external_id = getattr(value, "external_id", None)
    if isinstance(space, str) and isinstance(external_id, str):
        return [value]
    return list(value)


def serialize_instance(instance: Any) -> dict[str, Any]:
    """Serialize a node/edge with properties via the SDK dump."""
    if hasattr(instance, "dump"):
        return instance.dump(camel_case=True)
    return {
        "space": getattr(instance, "space", None),
        "externalId": getattr(instance, "external_id", None),
        "instanceType": getattr(instance, "instance_type", None),
    }


def build_instance_filter(
    *,
    source: ViewId,
    instance_type: InstanceType,
    instance_space: str | None = None,
    extra_filter: dict[str, Any] | None = None,
) -> Filter:
    """Combine hasData(view) with optional instance space and user filter."""
    parts: list[Filter] = [HasData(views=[source])]
    space = optional_str(instance_space)
    if space is not None:
        parts.append(Equals(property=[instance_type, "space"], value=space))
    if extra_filter:
        parts.append(Filter.load(extra_filter))
    if len(parts) == 1:
        return parts[0]
    return And(*parts)


def dump_maybe(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "dump"):
        return value.dump(camel_case=True)
    if isinstance(value, list):
        return [dump_maybe(v) for v in value]
    return value
