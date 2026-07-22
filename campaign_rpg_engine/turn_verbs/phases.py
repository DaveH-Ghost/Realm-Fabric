"""Optional pathing before turn verb execution (opt-in per registered verb)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from campaign_rpg_engine.action_outcome import ActionOutcome
from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area
from campaign_rpg_engine.grid import chebyshev_distance
from campaign_rpg_engine.move_target import (
    ResolvedMoveTarget,
    entity_goal_blocks_movement,
    format_move_arrival_message,
    format_move_arrival_passive,
    format_move_towards_message,
    format_move_towards_passive,
)
from campaign_rpg_engine.occupancy import find_blocker_between, is_tile_enterable
from campaign_rpg_engine.pathfinding import find_path, walk_with_pathfinding
from campaign_rpg_engine.perception import nearest_standable_in_chebyshev_range
from campaign_rpg_engine.turn_verbs.registry import (
    get_turn_verb_registration,
    resolve_verb_path_range,
    run_turn_verb,
)

if TYPE_CHECKING:
    from campaign_rpg_engine.llm.schemas import AgentCompoundTurn
    from campaign_rpg_engine.session import Session


@dataclass(frozen=True)
class VerbPhaseResult:
    """Compound-turn verb: optional path move, then verb outcome."""

    path_move: ActionOutcome | None
    outcome: ActionOutcome | str


def _in_range_of_agent(agent: Agent, target: Agent, action_range: int) -> bool:
    return chebyshev_distance(agent.position, target.position) <= action_range


def _too_far_message(target: Agent, verb_id: str) -> ActionOutcome:
    return ActionOutcome(
        result=(f"Unfortunately you are too far from {target.name} to {verb_id}."),
    )


def _build_agent_path_move_outcome(
    agent: Agent,
    area: Area,
    target: Agent,
    start_pos: tuple[int, int],
    standable_goal: tuple[int, int] | None,
) -> ActionOutcome | None:
    if agent.position == start_pos:
        return None

    resolved = ResolvedMoveTarget(
        target.position,
        entity_id=target.id,
        entity_name=target.name,
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
            target.position,
            agent.id,
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


def _path_agent_toward_agent(
    agent: Agent,
    area: Area,
    target: Agent,
    action_range: int,
    verb_id: str,
    *,
    session: Session | None = None,
    trigger_fired: set[tuple[str, str, str]] | None = None,
) -> tuple[ActionOutcome | None, ActionOutcome | None]:
    """
    Spend move budget pathing toward *target* for a ranged turn verb.

    Returns ``(path_move_outcome, error_outcome)``.
    """
    if _in_range_of_agent(agent, target, action_range):
        return None, None

    start_pos = agent.position
    goal = nearest_standable_in_chebyshev_range(
        agent,
        area,
        target.position,
        action_range,
    )
    if goal is None:
        return None, _too_far_message(target, verb_id)

    if agent.position == goal:
        path_move = _build_agent_path_move_outcome(agent, area, target, start_pos, goal)
        return path_move, _too_far_message(target, verb_id)

    if agent.move_speed is None:
        if not is_tile_enterable(area, goal, agent.id):
            return None, _too_far_message(target, verb_id)

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

        path_move = _build_agent_path_move_outcome(agent, area, target, start_pos, goal)
        if _in_range_of_agent(agent, target, action_range):
            return path_move, None
        return path_move, _too_far_message(target, verb_id)

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

    path_move = _build_agent_path_move_outcome(agent, area, target, start_pos, goal)
    if _in_range_of_agent(agent, target, action_range):
        return path_move, None
    return path_move, _too_far_message(target, verb_id)


def verb_registration_has_pathing(reg) -> bool:
    """True when a registration opts into agent-target pathing."""
    if reg is None or reg.path_target_from_turn is None:
        return False
    return reg.path_range is not None or reg.path_range_from_turn is not None


def verb_turn_has_pathing(turn: AgentCompoundTurn) -> bool:
    """True when this verb turn opts into engine pathing (usually replaces explicit move)."""
    if turn.action != "verb":
        return False
    verb_id = (turn.verb or "").strip()
    if not verb_id:
        return False
    reg = get_turn_verb_registration(verb_id)
    if not verb_registration_has_pathing(reg):
        return False
    return bool(reg.path_target_from_turn(turn))


def explicit_move_reaches_agent_range(
    agent: Agent,
    area: Area,
    *,
    move: str,
    target_id: str,
    action_range: int,
) -> bool:
    """
    True when the compound ``move`` would leave the agent in Chebyshev range of *target_id*.

    Used so nav honors an explicit move that already achieves verb range,
    instead of replacing it with auto-pathing toward the target agent.
    """
    from campaign_rpg_engine.actions.move import simulate_move_final_position

    target = area.get_agent_by_id(target_id)
    if target is None:
        return False
    final = simulate_move_final_position(agent, area, move)
    if final is None:
        return False
    return chebyshev_distance(final, target.position) <= action_range


def run_turn_verb_phases(
    session: Session | None,
    agent: Agent,
    area: Area,
    turn: AgentCompoundTurn,
    *,
    trigger_fired: set[tuple[str, str, str]] | None = None,
) -> VerbPhaseResult:
    """Run optional pathing, then dispatch the registered turn verb."""
    verb_id = (turn.verb or "").strip()
    reg = get_turn_verb_registration(verb_id)
    if reg is None:
        return VerbPhaseResult(None, run_turn_verb(session, agent, area, turn))

    path_move: ActionOutcome | None = None
    if verb_registration_has_pathing(reg):
        action_range = resolve_verb_path_range(session, agent, area, turn, reg)
        target_id = (reg.path_target_from_turn(turn) or "").strip()
        if action_range is not None and target_id:
            target = area.get_agent_by_id(target_id)
            if target is not None and target.id != agent.id:
                path_move, path_err = _path_agent_toward_agent(
                    agent,
                    area,
                    target,
                    action_range,
                    verb_id,
                    session=session,
                    trigger_fired=trigger_fired,
                )
                if path_err is not None:
                    return VerbPhaseResult(path_move, path_err)

    return VerbPhaseResult(path_move, run_turn_verb(session, agent, area, turn))
