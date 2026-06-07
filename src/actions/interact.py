"""
interact.py

Declarative object interactions for V0.2 Section 3.
"""

from src.action_outcome import ActionOutcome
from src.agent import Agent
from src.grid import chebyshev_distance
from src.object import Object
from src.object_action import ObjectAction
from src.object_effects import apply_effects
from src.perception import is_object_in_passive_vision
from src.world import World


def _format_template(template: str, *, actor: str, object_name: str) -> str:
    return (
        template.replace("{actor}", actor).replace("{object}", object_name)
    )


def interact(
    agent: Agent,
    world: World,
    target_id: str,
    action_name: str,
) -> ActionOutcome:
    """Execute an object interaction from the action phase."""
    obj = world.get_object_by_id(target_id)
    if obj is None:
        return ActionOutcome(
            result=(
                "This action wasn't recognized, ERR:UNKNOWN_INTERACT, "
                "that object does not exist."
            ),
        )

    action = obj.actions.get(action_name)
    if action is None:
        return ActionOutcome(
            result=(
                "This action wasn't recognized, ERR:UNKNOWN_INTERACT, "
                f"'{action_name}' is not an action on {obj.name}."
            ),
        )

    if not is_object_in_passive_vision(agent, world, target_id):
        return ActionOutcome(
            result=(
                "This action wasn't recognized, ERR:INTERACT_NOT_VISIBLE, "
                f"you cannot interact with {obj.name} from here."
            ),
        )

    if not _in_range(agent, obj, action):
        return ActionOutcome(
            result=(
                "This action wasn't recognized, ERR:INTERACT_OUT_OF_RANGE, "
                f"you are too far from {obj.name} to {action_name}."
            ),
        )

    if action.effects:
        apply_effects(world, agent, obj, list(action.effects))

    return ActionOutcome(
        result=_format_template(
            action.result, actor=agent.name, object_name=obj.name
        ),
        passive_result=_format_template(
            action.passive_result, actor=agent.name, object_name=obj.name
        ),
    )


def _in_range(agent: Agent, obj: Object, action: ObjectAction) -> bool:
    return chebyshev_distance(agent.position, obj.position) <= action.range
