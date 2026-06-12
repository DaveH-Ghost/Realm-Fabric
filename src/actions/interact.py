"""
interact.py

Declarative object interactions for V0.2 Section 3.

Result/passive templates support ``{actor}``, ``{object}``, ``{start}``, and
``{end}`` — object position before and after effects run (same value if nothing moved).
"""

from src.action_outcome import ActionOutcome
from src.agent import Agent
from src.coordinates import format_coordinate
from src.grid import chebyshev_distance
from src.object import Object
from src.object_action import ObjectAction
from src.object_effects import apply_effects
from src.perception import is_object_in_passive_vision
from src.area import Area


def _format_template(
    template: str,
    *,
    actor: str,
    object_name: str,
    start_position: tuple[int, int],
    end_position: tuple[int, int],
) -> str:
    start = format_coordinate(*start_position)
    end = format_coordinate(*end_position)
    return (
        template.replace("{actor}", actor)
        .replace("{object}", object_name)
        .replace("{start}", start)
        .replace("{end}", end)
    )


def interact(
    agent: Agent,
    area: Area,
    target_id: str,
    action_name: str,
) -> ActionOutcome:
    """Execute an object interaction from the action phase."""
    obj = area.get_object_by_id(target_id)
    if obj is None:
        return ActionOutcome(result="That object does not exist.")

    action = obj.actions.get(action_name)
    if action is None:
        return ActionOutcome(
            result=(
                f"'{action_name}' is not an action you can perform on {obj.name}."
            ),
        )

    if not is_object_in_passive_vision(agent, area, target_id):
        return ActionOutcome(
            result=f"You can't reach {obj.name} from here.",
        )

    if not _in_range(agent, obj, action):
        return ActionOutcome(
            result=(
                f"Unfortunately you are too far from {obj.name} to {action_name}."
            ),
        )

    start_position = obj.position
    if action.effects:
        apply_effects(area, agent, obj, list(action.effects))
    end_position = obj.position

    template_kwargs = {
        "actor": agent.name,
        "object_name": obj.name,
        "start_position": start_position,
        "end_position": end_position,
    }
    return ActionOutcome(
        result=_format_template(action.result, **template_kwargs),
        passive_result=_format_template(action.passive_result, **template_kwargs),
    )


def _in_range(agent: Agent, obj: Object, action: ObjectAction) -> bool:
    return chebyshev_distance(agent.position, obj.position) <= action.range
