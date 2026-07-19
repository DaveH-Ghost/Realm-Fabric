"""

interact.py



Declarative object interactions for V0.2 Section 3.



Result/passive templates support placeholders documented in

``src.interact_templates`` (e.g. ``{actor}``, ``{object}``, ``{object_start}``).

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from campaign_rpg_engine.action_outcome import ActionOutcome
from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area
from campaign_rpg_engine.interaction_handlers.registry import run_interaction_handler
from campaign_rpg_engine.move_target import (
    ResolvedMoveTarget,
    entity_goal_blocks_movement,
    format_move_arrival_message,
    format_move_arrival_passive,
    format_move_towards_message,
    format_move_towards_passive,
)
from campaign_rpg_engine.object import Object, chebyshev_distance_to_object
from campaign_rpg_engine.object_action import ObjectAction
from campaign_rpg_engine.occupancy import (
    find_blocker_between,
    footprint_tiles_for_entity,
    is_tile_enterable,
)
from campaign_rpg_engine.pathfinding import find_path, walk_with_pathfinding
from campaign_rpg_engine.perception import (
    is_object_in_passive_vision,
    nearest_standable_in_interact_range,
)
from campaign_rpg_engine.templates.interact_templates import (
    InteractTemplateContext,
    format_interact_template,
)

if TYPE_CHECKING:
    from campaign_rpg_engine.session import Session


@dataclass(frozen=True)
class InteractPhaseResult:
    """Compound-turn interact: optional path move, then interact outcome."""

    path_move: ActionOutcome | None

    outcome: ActionOutcome


def _resolve_agent_area(
    session: Session | None,
    agent_id: str,
    fallback: str | None,
) -> str:

    if session is not None:
        return session.agent_area.get(agent_id) or fallback or ""

    return fallback or ""


def _in_range(agent: Agent, obj: Object, action: ObjectAction) -> bool:
    return chebyshev_distance_to_object(agent.position, obj) <= action.range


def _too_far_message(obj: Object, action: ObjectAction) -> ActionOutcome:

    return ActionOutcome(
        result=(f"Unfortunately you are too far from {obj.name} to {action.name}."),
    )


def _build_interact_path_move_outcome(
    agent: Agent,
    area: Area,
    obj: Object,
    start_pos: tuple[int, int],
    standable_goal: tuple[int, int] | None,
) -> ActionOutcome | None:
    """First-person move result when interact pathing changed the agent's tile."""

    if agent.position == start_pos:
        return None

    resolved = ResolvedMoveTarget(
        obj.position,
        entity_id=obj.id,
        entity_name=obj.name,
    )

    goal_blocks = entity_goal_blocks_movement(area, resolved, agent.id)

    if standable_goal is not None and agent.position == standable_goal:
        return ActionOutcome(
            result=format_move_arrival_message(
                resolved,
                agent.position,
                goal_blocks_movement=goal_blocks,
            ),
            passive_result=format_move_arrival_passive(
                agent.name,
                resolved,
                agent.position,
                goal_blocks_movement=goal_blocks,
            ),
        )

    blocker = None

    if standable_goal is not None and not find_path(agent.position, standable_goal, area, agent.id):
        blocker = find_blocker_between(
            area,
            agent.position,
            obj.position,
            agent.id,
            ignore_tiles=footprint_tiles_for_entity(area, obj.id),
        )

    return ActionOutcome(
        result=format_move_towards_message(
            resolved,
            agent.position,
            blocker_name=blocker,
            area=area,
        ),
        passive_result=format_move_towards_passive(
            agent.name,
            resolved,
            agent.position,
            area=area,
        ),
    )


def _path_agent_for_interact(
    agent: Agent,
    area: Area,
    obj: Object,
    action: ObjectAction,
    *,
    session: Session | None = None,
    trigger_fired=None,
) -> tuple[tuple[int, int] | None, ActionOutcome | None]:
    """

    Spend move budget pathing toward *obj* for *action*.



    Returns ``(standable_goal, error)`` where *error* is set when interact cannot

    proceed after pathing.

    """

    if _in_range(agent, obj, action):
        return None, None

    goal = nearest_standable_in_interact_range(agent, area, obj, action)

    if goal is None:
        return None, _too_far_message(obj, action)

    if agent.position == goal:
        return goal, _too_far_message(obj, action)

    if agent.move_speed is None:
        if not is_tile_enterable(area, goal, agent.id):
            return goal, _too_far_message(obj, action)

        path = find_path(agent.position, goal, area, agent.id)
        if session is not None and trigger_fired is not None and len(path) > 1:
            from campaign_rpg_engine.triggers import advance_agent_along_path

            advance_agent_along_path(
                agent,
                area,
                path,
                session=session,
                trigger_fired=trigger_fired,
            )
        else:
            agent.position = goal
            if session is not None and trigger_fired is not None:
                from campaign_rpg_engine.triggers import evaluate_triggers_at_position

                evaluate_triggers_at_position(session, agent, area, trigger_fired)

        if _in_range(agent, obj, action):
            return goal, None

        return goal, _too_far_message(obj, action)

    final_pos, _reached, path = walk_with_pathfinding(
        agent.position,
        goal,
        agent.move_speed,
        area,
        agent.id,
    )

    if session is not None and trigger_fired is not None:
        from campaign_rpg_engine.triggers import advance_agent_along_path

        final_pos, _halted = advance_agent_along_path(
            agent,
            area,
            path,
            session=session,
            trigger_fired=trigger_fired,
        )
    else:
        agent.position = final_pos

    if _in_range(agent, obj, action):
        return goal, None

    return goal, _too_far_message(obj, action)


def _execute_interact_action(
    agent: Agent,
    area: Area,
    obj: Object,
    action: ObjectAction,
    action_name: str,
    *,
    session: Session | None = None,
    source_area_id: str | None = None,
) -> ActionOutcome:

    if not _in_range(agent, obj, action):
        return ActionOutcome(
            result=(f"Unfortunately you are too far from {obj.name} to {action_name}."),
        )

    object_area = source_area_id or ""

    actor_start_area = _resolve_agent_area(session, agent.id, source_area_id)

    object_start = obj.position

    actor_start = agent.position

    if action.handler_id:
        handler_result = run_interaction_handler(session, area, agent, obj, action)
        if isinstance(handler_result, ActionOutcome):
            return handler_result
        if handler_result:
            return ActionOutcome(result=handler_result)

    template_ctx = InteractTemplateContext(
        actor=agent.name,
        object_name=obj.name,
        object_start=object_start,
        object_end=obj.position,
        actor_start=actor_start,
        actor_end=agent.position,
        object_start_area=object_area,
        object_end_area=object_area,
        actor_start_area=actor_start_area,
        actor_end_area=_resolve_agent_area(session, agent.id, source_area_id),
    )

    return ActionOutcome(
        result=format_interact_template(action.result, template_ctx),
        passive_result=format_interact_template(action.passive_result, template_ctx),
    )


def interact_phases(
    agent: Agent,
    area: Area,
    target_id: str,
    action_name: str,
    *,
    session: Session | None = None,
    source_area_id: str | None = None,
    trigger_fired=None,
) -> InteractPhaseResult:
    """Run interact with separate path-move and action outcomes for compound turns."""

    obj = area.get_object_by_id(target_id)

    if obj is None:
        return InteractPhaseResult(
            path_move=None,
            outcome=ActionOutcome(result="That object does not exist."),
        )

    action = obj.actions.get(action_name)

    if action is None:
        available = sorted(
            name for name, act in obj.actions.items() if act.kind != "trigger" and act.enabled
        )
        if available:
            listed = ", ".join(repr(name) for name in available)
            hint = (
                f" Available on {obj.name}: {listed}."
                " For roleplay that is not listed, use action emote instead."
            )
        else:
            hint = f" {obj.name} has no interact actions. For roleplay, use action emote instead."
        return InteractPhaseResult(
            path_move=None,
            outcome=ActionOutcome(
                result=(f"'{action_name}' is not an action you can perform on {obj.name}.{hint}"),
            ),
        )

    if action.kind == "trigger":
        return InteractPhaseResult(
            path_move=None,
            outcome=ActionOutcome(
                result=(f"'{action_name}' is a trigger, not an interact action on {obj.name}."),
            ),
        )

    if not action.enabled:
        return InteractPhaseResult(
            path_move=None,
            outcome=ActionOutcome(
                result=(f"'{action_name}' is not available on {obj.name}."),
            ),
        )

    if not is_object_in_passive_vision(agent, area, target_id):
        return InteractPhaseResult(
            path_move=None,
            outcome=ActionOutcome(
                result=f"You can't reach {obj.name} from here.",
            ),
        )

    start_pos = agent.position

    standable_goal, path_err = _path_agent_for_interact(
        agent,
        area,
        obj,
        action,
        session=session,
        trigger_fired=trigger_fired,
    )

    path_move = _build_interact_path_move_outcome(
        agent,
        area,
        obj,
        start_pos,
        standable_goal,
    )

    if path_err is not None:
        return InteractPhaseResult(path_move=path_move, outcome=path_err)

    return InteractPhaseResult(
        path_move=path_move,
        outcome=_execute_interact_action(
            agent,
            area,
            obj,
            action,
            action_name,
            session=session,
            source_area_id=source_area_id,
        ),
    )


def interact(
    agent: Agent,
    area: Area,
    target_id: str,
    action_name: str,
    *,
    session: Session | None = None,
    source_area_id: str | None = None,
) -> ActionOutcome:
    """Execute an object interaction from the action phase."""

    return interact_phases(
        agent,
        area,
        target_id,
        action_name,
        session=session,
        source_area_id=source_area_id,
    ).outcome
