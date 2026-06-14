"""
move.py

Coordinate and entity-id move for V0.2 / V0.4.0a–b.

V0.4.0a: ``move_target`` may be ``x,y`` or ``agent_*`` / ``obj_*``.
V0.4.0b: when ``agent.move_speed`` is set, walk up to N steps (5e pathing).
"""

from src.action_outcome import ActionOutcome
from src.agent import Agent
from src.coordinates import format_coordinate
from src.move_target import (
    MoveTargetError,
    format_move_arrival_message,
    format_move_towards_message,
    format_move_towards_passive,
    resolve_move_target,
)
from src.pathing import walk_towards
from src.area import Area


def move(agent: Agent, area: Area, target: str) -> ActionOutcome:
    """Move the agent toward a coordinate or entity-id target tile."""
    try:
        resolved = resolve_move_target(area, target)
    except MoveTargetError as exc:
        return ActionOutcome(
            result=f"This action wasn't recognized, {exc}",
        )

    goal = resolved.position
    goal_label = format_coordinate(*goal)

    if not area.is_valid_position(goal):
        return ActionOutcome(
            result=(
                "This action wasn't recognized, ERR:INVALID_COORDINATES, "
                f"{goal_label} is outside the room."
            ),
        )

    if agent.position == goal:
        return ActionOutcome(
            result=f"You are already at {goal_label}.",
        )

    if agent.move_speed is None:
        agent.position = goal
        end_label = format_coordinate(*agent.position)
        return ActionOutcome(
            result=format_move_arrival_message(resolved),
            passive_result=f"{agent.name} moves to {end_label}.",
        )

    final_pos, reached = walk_towards(agent.position, goal, agent.move_speed)
    if not area.is_valid_position(final_pos):
        return ActionOutcome(
            result=(
                "This action wasn't recognized, ERR:INVALID_COORDINATES, "
                f"{format_coordinate(*final_pos)} is outside the room."
            ),
        )

    agent.position = final_pos
    end_label = format_coordinate(*final_pos)

    if reached:
        return ActionOutcome(
            result=format_move_arrival_message(resolved),
            passive_result=f"{agent.name} moves to {end_label}.",
        )

    return ActionOutcome(
        result=format_move_towards_message(resolved),
        passive_result=format_move_towards_passive(agent.name, resolved, final_pos),
    )
