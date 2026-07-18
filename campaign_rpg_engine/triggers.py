"""Path-step triggers for V0.6.0e / V0.6.1."""

from __future__ import annotations

from typing import TYPE_CHECKING

from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area
from campaign_rpg_engine.interact_templates import InteractTemplateContext, format_interact_template
from campaign_rpg_engine.interaction_handlers.registry import run_interaction_handler
from campaign_rpg_engine.object import Object, chebyshev_distance_to_object
from campaign_rpg_engine.object_action import ObjectAction

if TYPE_CHECKING:
    from campaign_rpg_engine.session import Session

TriggerFiredSet = set[tuple[str, str, str]]


def advance_agent_along_path(
    agent: Agent,
    area: Area,
    path: list[tuple[int, int]],
    *,
    session: Session,
    trigger_fired: TriggerFiredSet,
) -> tuple[tuple[int, int], bool]:
    """
    Step the agent along *path*[1:], firing triggers at each tile.

    Returns ``(final_position, halted)`` where *halted* is True when a trigger
    with ``halt_movement`` stopped the walk early.
    """
    if len(path) <= 1:
        return agent.position, False

    halted = False
    for tile in path[1:]:
        agent.position = tile
        if evaluate_triggers_at_position(session, agent, area, trigger_fired):
            halted = True
            break
    return agent.position, halted


def evaluate_triggers_at_position(
    session: Session,
    agent: Agent,
    area: Area,
    trigger_fired: TriggerFiredSet,
) -> bool:
    """Fire triggers for the agent's current tile. Returns True if movement halts.

    Range is Chebyshev distance to the object's nearest footprint tile, so
    multi-tile ``width`` / ``height`` objects work as tripwires and zone triggers.
    """
    halted = False
    position = agent.position
    source_area_id = session.agent_area.get(agent.id)

    for obj in list(area.get_objects()):
        for action_name, action in list(obj.actions.items()):
            if action.kind != "trigger":
                continue
            if not action.enabled:
                continue
            if agent.id in action.trigger_exceptions:
                continue
            key = (agent.id, obj.id, action_name)
            if key in trigger_fired:
                continue
            if chebyshev_distance_to_object(position, obj) > action.range:
                continue

            trigger_fired.add(key)
            _fire_trigger(
                session,
                agent,
                area,
                obj,
                action_name,
                action,
                source_area_id=source_area_id,
            )
            if action.halt_movement:
                halted = True
    return halted


def _fire_trigger(
    session: Session,
    agent: Agent,
    area: Area,
    obj: Object,
    action_name: str,
    action: ObjectAction,
    *,
    source_area_id: str | None,
) -> None:
    object_start = obj.position
    actor_start = agent.position
    template_ctx = InteractTemplateContext(
        actor=agent.name,
        object_name=obj.name,
        object_start=object_start,
        object_end=object_start,
        actor_start=actor_start,
        actor_end=agent.position,
        object_start_area=source_area_id or "",
        object_end_area=source_area_id or "",
        actor_start_area=source_area_id or "",
        actor_end_area=source_area_id or "",
    )
    text = format_interact_template(action.passive_result, template_ctx).strip()
    if text:
        session.emit_area_event(text)

    if action.handler_id:
        run_interaction_handler(session, area, agent, obj, action)
    elif action.delete_after_trigger and area.get_object_by_id(obj.id) is not None:
        area.remove_object(obj.id)
