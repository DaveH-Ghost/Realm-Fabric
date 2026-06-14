"""
session_area_edit.py

Parse and apply session-level area CRUD (V0.4.0c2+).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from src.area import Area, GridBounds, create_area
from src.area_edit import parse_field_tokens, tokenize_args

if TYPE_CHECKING:
    from src.session import Session

_AREA_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class AreaMutationResult:
    ok: bool
    message: str
    area_id: Optional[str] = None


def validate_area_id(area_id: str) -> Optional[str]:
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


def _parse_bounds_fields(fields: dict[str, str]) -> tuple[Optional[GridBounds], Optional[str]]:
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


def _entities_outside_bounds(area: Area, bounds: GridBounds) -> Optional[str]:
    for agent in area.agents:
        x, y = agent.position
        if not (bounds.min_x <= x <= bounds.max_x and bounds.min_y <= y <= bounds.max_y):
            return (
                f"Agent {agent.name} ({agent.id}) at ({x}, {y}) "
                f"would be outside the new bounds."
            )
    for obj in area.get_objects():
        x, y = obj.position
        if not (bounds.min_x <= x <= bounds.max_x and bounds.min_y <= y <= bounds.max_y):
            return (
                f"Object {obj.name} ({obj.id}) at ({x}, {y}) "
                f"would be outside the new bounds."
            )
    return None


def create_area_from_args(session: Session, arg: str) -> AreaMutationResult:
    """
    ``create-area id <area_id> [desc "..."] [width N] [height N]``
    or ``min-x … max-x …`` corner bounds.
    """
    tokens, err = tokenize_args(arg)
    if err:
        return AreaMutationResult(ok=False, message=err)
    if not tokens:
        return AreaMutationResult(
            ok=False,
            message=(
                'Usage: create-area id <area_id> [desc "..."] '
                "[width N] [height N]  (defaults: 5x5 grid)"
            ),
        )

    fields, err = parse_field_tokens(
        tokens,
        {"id", "desc", "width", "height", "min-x", "min-y", "max-x", "max-y"},
    )
    if err:
        return AreaMutationResult(ok=False, message=err)
    if "id" not in fields:
        return AreaMutationResult(ok=False, message="create-area requires id <area_id>.")

    area_id = fields["id"]
    id_err = validate_area_id(area_id)
    if id_err:
        return AreaMutationResult(ok=False, message=id_err)
    if area_id in session.areas:
        return AreaMutationResult(ok=False, message=f"Area {area_id!r} already exists.")

    bounds, err = _parse_bounds_fields(fields)
    if err:
        return AreaMutationResult(ok=False, message=err)
    assert bounds is not None

    description = fields.get("desc", "")
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


def edit_area_from_args(session: Session, arg: str) -> AreaMutationResult:
    """
    ``edit-area <area_id> [desc "..."] [width N] [height N]`` or corner bounds.
    """
    tokens, err = tokenize_args(arg)
    if err:
        return AreaMutationResult(ok=False, message=err)
    if not tokens:
        return AreaMutationResult(
            ok=False,
            message='Usage: edit-area <area_id> [desc "..."] [width N] [height N]',
        )

    area_id = tokens[0]
    id_err = validate_area_id(area_id)
    if id_err:
        return AreaMutationResult(ok=False, message=id_err)
    area = session.areas.get(area_id)
    if area is None:
        return AreaMutationResult(ok=False, message=f"Unknown area {area_id!r}.")

    fields, err = parse_field_tokens(
        tokens[1:],
        {"desc", "width", "height", "min-x", "min-y", "max-x", "max-y"},
    )
    if err:
        return AreaMutationResult(ok=False, message=err)
    if not fields:
        return AreaMutationResult(
            ok=False,
            message="edit-area requires at least one field to change.",
        )

    if "desc" in fields:
        area.area_description = fields["desc"]

    if any(k in fields for k in ("width", "height", "min-x", "min-y", "max-x", "max-y")):
        merged: dict[str, str] = {}
        if any(k in fields for k in ("min-x", "min-y", "max-x", "max-y")):
            merged["min-x"] = fields.get("min-x", str(area.bounds.min_x))
            merged["min-y"] = fields.get("min-y", str(area.bounds.min_y))
            merged["max-x"] = fields.get("max-x", str(area.bounds.max_x))
            merged["max-y"] = fields.get("max-y", str(area.bounds.max_y))
        else:
            merged["min-x"] = str(area.bounds.min_x)
            merged["min-y"] = str(area.bounds.min_y)
            merged["width"] = fields.get("width", str(area.bounds.width))
            merged["height"] = fields.get("height", str(area.bounds.height))
        bounds, err = _parse_bounds_fields(merged)
        if err:
            return AreaMutationResult(ok=False, message=err)
        assert bounds is not None
        outside = _entities_outside_bounds(area, bounds)
        if outside:
            return AreaMutationResult(ok=False, message=outside)
        area.bounds = bounds

    return AreaMutationResult(
        ok=True,
        message=f"Updated area {area_id!r}.",
        area_id=area_id,
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
