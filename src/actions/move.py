"""
move.py

Coordinate move for V0.2.

V0.2: parse/normalize target -> validate in-bounds -> set agent.position directly.
No pathing, blockers, or tiles-passed-through updates yet (future pathing hooks here).
"""

from src.action_outcome import ActionOutcome
from src.agent import Agent
from src.coordinates import CoordinateParseError, format_coordinate, parse_coordinate_target
from src.area import Area


def move(agent: Agent, area: Area, target: str) -> ActionOutcome:
    """Move the agent to the parsed coordinate target."""
    try:
        x, y = parse_coordinate_target(target)
    except CoordinateParseError as exc:
        return ActionOutcome(
            result=f"This action wasn't recognized, {exc}",
        )

    new_pos = (x, y)
    label = format_coordinate(x, y)

    if not area.is_valid_position(new_pos):
        return ActionOutcome(
            result=(
                "This action wasn't recognized, ERR:INVALID_COORDINATES, "
                f"{label} is outside the room."
            ),
        )

    if agent.position == new_pos:
        return ActionOutcome(
            result=f"You are already at {label}.",
        )

    agent.position = new_pos
    return ActionOutcome(
        result=f"You moved to {label}.",
        passive_result=f"{agent.name} moves to {label}.",
    )
