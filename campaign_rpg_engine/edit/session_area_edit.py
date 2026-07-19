"""
session_area_edit.py

Typed session-level area CRUD (V0.4.0c2+).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from campaign_rpg_engine.area import Area, GridBounds, create_area

if TYPE_CHECKING:
    from campaign_rpg_engine.session import Session

_AREA_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class AreaMutationResult:
    ok: bool
    message: str
    area_id: str | None = None


def validate_area_id(area_id: str) -> str | None:
    """Return an error message if ``area_id`` is invalid."""
    cleaned = area_id.strip()
    if not cleaned:
        return "Area id cannot be empty."
    if not _AREA_ID_RE.fullmatch(cleaned):
        return (
            f"Invalid area id {area_id!r}. "
            "Use lowercase letters, digits, and underscores (e.g. hall, roof_01)."
        )
    return None


def parse_bounds_fields(fields: dict[str, str]) -> tuple[GridBounds | None, str | None]:
    has_corner = "max-x" in fields or "max-y" in fields
    has_size = "width" in fields or "height" in fields

    if has_corner and has_size:
        return None, "Use either width/height or min-x/min-y/max-x/max-y, not both."

    if has_corner:
        try:
            min_x = int(fields.get("min-x", "0"))
            min_y = int(fields.get("min-y", "0"))
            max_x = int(fields["max-x"])
            max_y = int(fields["max-y"])
        except KeyError:
            return None, "Grid bounds require min-x, min-y, max-x, and max-y."
        except ValueError:
            return None, "Grid bounds must be integers."
        try:
            return GridBounds(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y), None
        except ValueError as exc:
            return None, str(exc)

    width = int(fields.get("width", "5"))
    height = int(fields.get("height", "5"))
    if width < 1 or height < 1:
        return None, "width and height must be at least 1."
    try:
        min_x = int(fields.get("min-x", "0"))
        min_y = int(fields.get("min-y", "0"))
    except ValueError:
        return None, "min-x and min-y must be integers."
    return GridBounds(
        min_x=min_x,
        min_y=min_y,
        max_x=min_x + width - 1,
        max_y=min_y + height - 1,
    ), None


def entities_outside_bounds(area: Area, bounds: GridBounds) -> str | None:
    for agent in area.agents:
        x, y = agent.position
        if not (bounds.min_x <= x <= bounds.max_x and bounds.min_y <= y <= bounds.max_y):
            return f"Agent {agent.name} ({agent.id}) at ({x}, {y}) would be outside the new bounds."
    for obj in area.get_objects():
        from campaign_rpg_engine.object import object_footprint_tiles

        for x, y in object_footprint_tiles(obj):
            if not (bounds.min_x <= x <= bounds.max_x and bounds.min_y <= y <= bounds.max_y):
                return (
                    f"Object {obj.name} ({obj.id}) footprint tile ({x}, {y}) "
                    f"would be outside the new bounds."
                )
    return None


def create_area_in_session(
    session: Session,
    area_id: str,
    *,
    description: str = "",
    width: int = 5,
    height: int = 5,
    min_x: int = 0,
    min_y: int = 0,
    bounds: GridBounds | None = None,
) -> AreaMutationResult:
    """Create a new area (same rules as ``create-area`` CLI)."""
    id_err = validate_area_id(area_id)
    if id_err:
        return AreaMutationResult(ok=False, message=id_err)
    if area_id in session.areas:
        return AreaMutationResult(ok=False, message=f"Area {area_id!r} already exists.")

    if bounds is None:
        if width < 1 or height < 1:
            return AreaMutationResult(ok=False, message="width and height must be at least 1.")
        bounds = GridBounds(
            min_x=min_x,
            min_y=min_y,
            max_x=min_x + width - 1,
            max_y=min_y + height - 1,
        )

    session.areas[area_id] = create_area(
        width=bounds.width,
        height=bounds.height,
        min_x=bounds.min_x,
        min_y=bounds.min_y,
        area_description=description,
    )
    session.active_area_id = area_id
    return AreaMutationResult(
        ok=True,
        message=(
            f"Created area {area_id!r} ({bounds.width}x{bounds.height} grid). "
            f"Active area: {area_id}."
        ),
        area_id=area_id,
    )


def edit_area_in_session(
    session: Session,
    area_id: str,
    *,
    description: str | None = None,
    width: int | None = None,
    height: int | None = None,
    min_x: int | None = None,
    min_y: int | None = None,
    max_x: int | None = None,
    max_y: int | None = None,
) -> AreaMutationResult:
    """Update area description and/or grid bounds (typed API)."""
    cleaned = area_id.strip()
    id_err = validate_area_id(cleaned)
    if id_err:
        return AreaMutationResult(ok=False, message=id_err)
    area = session.areas.get(cleaned)
    if area is None:
        return AreaMutationResult(ok=False, message=f"Unknown area {cleaned!r}.")

    if (
        description is None
        and width is None
        and height is None
        and min_x is None
        and min_y is None
        and max_x is None
        and max_y is None
    ):
        return AreaMutationResult(
            ok=False,
            message="edit-area requires at least one field to change.",
        )

    if description is not None:
        area.area_description = description

    if any(v is not None for v in (width, height, min_x, min_y, max_x, max_y)):
        merged: dict[str, str] = {}
        if any(v is not None for v in (min_x, min_y, max_x, max_y)):
            merged["min-x"] = str(min_x if min_x is not None else area.bounds.min_x)
            merged["min-y"] = str(min_y if min_y is not None else area.bounds.min_y)
            merged["max-x"] = str(max_x if max_x is not None else area.bounds.max_x)
            merged["max-y"] = str(max_y if max_y is not None else area.bounds.max_y)
        else:
            merged["min-x"] = str(area.bounds.min_x)
            merged["min-y"] = str(area.bounds.min_y)
            merged["width"] = str(width if width is not None else area.bounds.width)
            merged["height"] = str(height if height is not None else area.bounds.height)
        bounds, err = parse_bounds_fields(merged)
        if err:
            return AreaMutationResult(ok=False, message=err)
        assert bounds is not None
        outside = entities_outside_bounds(area, bounds)
        if outside:
            return AreaMutationResult(ok=False, message=outside)
        area.bounds = bounds

    return AreaMutationResult(
        ok=True,
        message=f"Updated area {cleaned!r}.",
        area_id=cleaned,
    )


def delete_area_by_id(session: Session, area_id: str) -> AreaMutationResult:
    """Remove an empty area. Fails if it is the last area or has entities."""
    cleaned = area_id.strip()
    if not cleaned:
        return AreaMutationResult(ok=False, message="Usage: delete-area <area_id>")

    id_err = validate_area_id(cleaned)
    if id_err:
        return AreaMutationResult(ok=False, message=id_err)
    if cleaned not in session.areas:
        return AreaMutationResult(ok=False, message=f"Unknown area {cleaned!r}.")

    if len(session.areas) <= 1:
        return AreaMutationResult(
            ok=False,
            message="Cannot delete the last area in the session.",
        )

    area = session.areas[cleaned]
    if area.agents:
        names = ", ".join(a.name for a in area.agents)
        return AreaMutationResult(
            ok=False,
            message=f"Area {cleaned!r} still has agent(s): {names}. Move or delete them first.",
        )
    if area.get_objects():
        names = ", ".join(o.name for o in area.get_objects())
        return AreaMutationResult(
            ok=False,
            message=f"Area {cleaned!r} still has object(s): {names}. Delete them first.",
        )

    del session.areas[cleaned]
    if session.active_area_id == cleaned:
        session.active_area_id = sorted(session.areas)[0]

    return AreaMutationResult(
        ok=True,
        message=f"Deleted area {cleaned!r}. Active area: {session.active_area_id}.",
    )
