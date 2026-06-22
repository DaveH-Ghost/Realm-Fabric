"""
move_target.py

V0.4.0a — resolve compound-turn move targets: grid coordinates or entity ids.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.agent import Agent
from src.area import Area
from src.coordinates import CoordinateParseError, format_coordinate, parse_coordinate_target


class MoveTargetError(ValueError):
    """Raised when a move target cannot be resolved in the current area."""


@dataclass(frozen=True)
class ResolvedMoveTarget:
    """Target tile plus optional entity label when resolved from an id."""

    position: tuple[int, int]
    entity_id: str | None = None
    entity_name: str | None = None


def is_entity_move_target(target: str) -> bool:
    text = target.strip()
    return text.startswith("agent_") or text.startswith("obj_")


def validate_move_target_syntax(target: str) -> str:
    """
    Pydantic/schema check: coordinate ``x,y`` or entity id ``agent_*`` / ``obj_*``.

    Does not verify the entity exists (runtime check in ``resolve_move_target``).
    """
    text = target.strip()
    if not text:
        raise CoordinateParseError(
            "ERR:INVALID_TARGET: move requires a coordinate 'x,y' or entity id"
        )
    if is_entity_move_target(text):
        return text
    parse_coordinate_target(text)
    return text


def resolve_move_target(area: Area, target: str) -> ResolvedMoveTarget:
    """Resolve a move target string to an in-area grid position."""
    text = target.strip()
    if is_entity_move_target(text):
        obj = area.get_object_by_id(text)
        if obj is not None:
            return ResolvedMoveTarget(
                obj.position,
                entity_id=text,
                entity_name=obj.name,
            )
        other = area.get_agent_by_id(text)
        if other is not None:
            return ResolvedMoveTarget(
                other.position,
                entity_id=text,
                entity_name=other.name,
            )
        raise MoveTargetError(
            f"ERR:INVALID_TARGET: unknown entity id {text!r}"
        )

    try:
        position = parse_coordinate_target(text)
    except CoordinateParseError as exc:
        raise MoveTargetError(str(exc)) from exc
    return ResolvedMoveTarget(position)


def format_move_arrival_message(resolved: ResolvedMoveTarget) -> str:
    label = format_coordinate(*resolved.position)
    if resolved.entity_name:
        return f"You moved to {resolved.entity_name} at {label}."
    return f"You moved to {label}."


def format_move_target_label(resolved: ResolvedMoveTarget) -> str:
    """Human label for the move goal (entity name or coordinate)."""
    if resolved.entity_name:
        return resolved.entity_name
    return format_coordinate(*resolved.position)


def format_move_towards_message(resolved: ResolvedMoveTarget) -> str:
    return f"You moved towards {format_move_target_label(resolved)}."


def format_move_towards_passive(
    agent_name: str,
    resolved: ResolvedMoveTarget,
    stop_position: tuple[int, int],
) -> str:
    stop = format_coordinate(*stop_position)
    return (
        f"{agent_name} moves towards {format_move_target_label(resolved)}, "
        f"stopping at {stop}."
    )


def format_move_speed_line(
    move_speed: int,
    *,
    vision_units: str = "",
    units_per_tile: int | None = None,
) -> str:
    """One-line move budget for the compound prompt."""
    per_tile = 1 if units_per_tile is None else units_per_tile
    value = move_speed * per_tile
    unit_label = vision_units.strip()
    if unit_label:
        return f"Your move speed this turn is {value} {unit_label}."
    return f"Your move speed this turn is {value} step(s)."


def format_move_instructions(
    agent: Agent,
    area: Area,
    *,
    include_coordinate_moves: bool = True,
    vision_units: str = "",
    units_per_tile: int | None = None,
) -> str:
    """Move rules for the compound prompt (entity ids; optional coordinate bounds)."""
    lines: list[str] = []
    if include_coordinate_moves:
        lines.append(area.format_move_coordinate_rule())
    lines.append(
        "move may be an entity id (obj_* or agent_*) for that tile."
    )
    if agent.move_speed is not None:
        lines.append(
            format_move_speed_line(
                agent.move_speed,
                vision_units=vision_units,
                units_per_tile=units_per_tile,
            )
        )
    return "\n".join(lines)


DEFAULT_MOVE_INSTRUCTIONS_OPTIONS: dict[str, bool] = {
    "include_coordinate_moves": True,
}


def normalize_move_instructions_options(
    options: dict[str, object] | None,
) -> dict[str, bool]:
    """Merge *options* with defaults for move_instructions slot rendering."""
    merged = dict(DEFAULT_MOVE_INSTRUCTIONS_OPTIONS)
    if options:
        for key in DEFAULT_MOVE_INSTRUCTIONS_OPTIONS:
            if key in options:
                merged[key] = bool(options[key])
    return merged
