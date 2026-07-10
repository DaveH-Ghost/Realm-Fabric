"""
move_target.py

V0.4.0a — resolve compound-turn move targets: grid coordinates or entity ids.
"""

from __future__ import annotations

from dataclasses import dataclass

from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area
from campaign_rpg_engine.coordinates import CoordinateParseError, format_coordinate, parse_coordinate_target
from campaign_rpg_engine.grid import chebyshev_distance
from campaign_rpg_engine.object import chebyshev_distance_to_object
from campaign_rpg_engine.occupancy import entity_blocks_for_mover


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


def entity_goal_blocks_movement(
    area: Area,
    resolved: ResolvedMoveTarget,
    mover_id: str,
) -> bool:
    """True when the resolved entity blocks *mover_id* from standing on its tile."""
    if not resolved.entity_id:
        return False
    obj = area.get_object_by_id(resolved.entity_id)
    if obj is not None:
        return entity_blocks_for_mover(obj, mover_id)
    other = area.get_agent_by_id(resolved.entity_id)
    if other is not None:
        return entity_blocks_for_mover(other, mover_id)
    return False


def _step_label(distance: int) -> str:
    if distance == 1:
        return "1 step"
    return f"{distance} steps"


def format_move_arrival_message(
    resolved: ResolvedMoveTarget,
    agent_position: tuple[int, int],
    *,
    goal_blocks_movement: bool,
) -> str:
    if resolved.entity_name:
        if goal_blocks_movement and agent_position != resolved.position:
            return f"You have successfully moved next to {resolved.entity_name}."
        return f"You moved to {resolved.entity_name}."
    return f"You moved to {format_coordinate(*resolved.position)}."


def format_move_arrival_passive(
    agent_name: str,
    resolved: ResolvedMoveTarget,
    agent_position: tuple[int, int],
    *,
    goal_blocks_movement: bool,
) -> str:
    if resolved.entity_name:
        if goal_blocks_movement and agent_position != resolved.position:
            return f"{agent_name} moves next to {resolved.entity_name}."
        return f"{agent_name} moves to {resolved.entity_name}."
    end_label = format_coordinate(*agent_position)
    return f"{agent_name} moves to {end_label}."


def format_move_target_label(resolved: ResolvedMoveTarget) -> str:
    """Human label for the move goal (entity name or coordinate)."""
    if resolved.entity_name:
        return resolved.entity_name
    return format_coordinate(*resolved.position)


def format_already_at_message(
    resolved: ResolvedMoveTarget,
    agent_position: tuple[int, int],
    standable_goal: tuple[int, int],
    *,
    goal_blocks_movement: bool,
) -> str:
    if resolved.entity_name:
        if goal_blocks_movement and agent_position != resolved.position:
            return f"You are already next to {resolved.entity_name}."
        if agent_position == resolved.position:
            return f"You are already at {resolved.entity_name}."
        return f"You are already next to {resolved.entity_name}."
    if agent_position == standable_goal and standable_goal != resolved.position:
        here = format_coordinate(*agent_position)
        goal = format_coordinate(*resolved.position)
        return f"You are already at {here}, as close as you can get to {goal}."
    return f"You are already at {format_coordinate(*agent_position)}."


def format_unreachable_message(
    resolved: ResolvedMoveTarget,
    goal_label: str,
    blocker_name: str | None,
) -> str:
    if resolved.entity_name:
        label = resolved.entity_name
        if blocker_name:
            return f"You cannot reach {label}; {blocker_name} is blocking the way."
        return f"You cannot reach {label}; movement is fully blocked."
    if blocker_name:
        return (
            f"You cannot reach {goal_label}; "
            f"{blocker_name} is blocking the way."
        )
    return f"You cannot reach {goal_label}; movement is fully blocked."


def _entity_stop_distance(
    stop_position: tuple[int, int],
    resolved: ResolvedMoveTarget,
    area: Area | None,
) -> int:
    if resolved.entity_id and area is not None:
        obj = area.get_object_by_id(resolved.entity_id)
        if obj is not None:
            return chebyshev_distance_to_object(stop_position, obj)
    return chebyshev_distance(stop_position, resolved.position)


def format_move_towards_message(
    resolved: ResolvedMoveTarget,
    stop_position: tuple[int, int],
    *,
    blocker_name: str | None = None,
    area: Area | None = None,
) -> str:
    label = format_move_target_label(resolved)
    if resolved.entity_id:
        distance = _entity_stop_distance(stop_position, resolved, area)
        message = (
            f"You moved towards {label}; "
            f"you are still {_step_label(distance)} away."
        )
        if blocker_name:
            message = f"{message} {blocker_name} is blocking the way."
        return message
    stop = format_coordinate(*stop_position)
    return f"You moved towards {label}, stopping at {stop}."


def format_move_towards_passive(
    agent_name: str,
    resolved: ResolvedMoveTarget,
    stop_position: tuple[int, int],
    *,
    area: Area | None = None,
) -> str:
    label = format_move_target_label(resolved)
    if resolved.entity_id:
        distance = _entity_stop_distance(stop_position, resolved, area)
        return (
            f"{agent_name} moves towards {label}; "
            f"still {_step_label(distance)} away."
        )
    stop = format_coordinate(*stop_position)
    return (
        f"{agent_name} moves towards {label}, "
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
