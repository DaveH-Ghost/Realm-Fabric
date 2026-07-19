"""
simulation.py

Compound turn execution for V0.2.5.

Pipeline per agent turn:
  optional move → optional look → optional speak → optional turn action (interact / emote)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from campaign_rpg_engine.action_outcome import ActionOutcome
from campaign_rpg_engine.actions import do_emote, do_interact_phases, do_move, do_speak
from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area
from campaign_rpg_engine.llm.schemas import AgentCompoundTurn
from campaign_rpg_engine.memory import StepKind, TurnRecord, TurnStep
from campaign_rpg_engine.perception import perform_look as do_look
from campaign_rpg_engine.turn_verbs.phases import run_turn_verb_phases, verb_turn_has_pathing

if TYPE_CHECKING:
    from campaign_rpg_engine.session import Session


def next_turn_number_for_agent(agent: Agent) -> int:
    """Return the next per-agent sequential turn number for TurnRecord."""
    return agent.memory.turn_count + 1


def _composite_result(steps: list[TurnStep]) -> str:
    if not steps:
        return "You took no actions this turn."
    return "\n".join(step.result for step in steps)


def _make_step(
    kind: StepKind,
    reasoning: str,
    outcome: ActionOutcome,
    *,
    target: str | None = None,
    content: str | None = None,
) -> TurnStep:
    return TurnStep(
        kind=kind,
        reasoning=reasoning,
        target=target,
        content=content,
        result=outcome.result,
        passive_result=outcome.passive_result,
        passive_witness_exclude_agent_ids=outcome.passive_witness_exclude_agent_ids,
    )


def execute_nav_phase(
    agent: Agent,
    area: Area,
    turn: AgentCompoundTurn,
    *,
    session: Session | None = None,
    trigger_fired: set[tuple[str, str, str]] | None = None,
) -> list[TurnStep]:
    """Run optional move from compound turn. Commits position changes."""
    if turn.action == "interact" or verb_turn_has_pathing(turn):
        return []
    if not turn.move:
        return []

    outcome = do_move(
        agent,
        area,
        turn.move,
        session=session,
        trigger_fired=trigger_fired,
    )
    if session is not None:
        area_id = session.agent_area.get(agent.id)
        session._emit_event("agent_moved", agent=agent, area_id=area_id)
    return [
        _make_step(
            "move",
            turn.reasoning,
            outcome,
            target=turn.move,
        )
    ]


def execute_action_phase(
    agent: Agent,
    area: Area,
    turn: AgentCompoundTurn,
    *,
    session: Session | None = None,
    source_area_id: str | None = None,
    trigger_fired: set[tuple[str, str, str]] | None = None,
) -> list[TurnStep]:
    """Run optional look and turn action from compound turn."""
    steps: list[TurnStep] = []

    if turn.look:
        outcome = do_look(agent, area, turn.look)
        steps.append(
            _make_step(
                "look",
                turn.reasoning,
                outcome,
                target=turn.look,
            )
        )

    if turn.say and str(turn.say).strip():
        outcome = do_speak(agent, area, turn.say)
        steps.append(
            _make_step(
                "speak",
                turn.reasoning,
                outcome,
                content=turn.say,
            )
        )

    if turn.action == "interact":
        phases = do_interact_phases(
            agent,
            area,
            turn.target or "",
            turn.verb or "",
            session=session,
            source_area_id=source_area_id,
            trigger_fired=trigger_fired,
        )
        if phases.path_move is not None:
            steps.append(
                _make_step(
                    "move",
                    turn.reasoning,
                    phases.path_move,
                    target=turn.target,
                )
            )
        steps.append(
            _make_step(
                "interact",
                turn.reasoning,
                phases.outcome,
                target=turn.target,
                content=turn.verb,
            )
        )
    elif turn.action == "emote":
        outcome = do_emote(
            agent,
            area,
            turn.target or "",
            turn.verb or "",
        )
        steps.append(
            _make_step(
                "emote",
                turn.reasoning,
                outcome,
                target=turn.target,
                content=turn.verb,
            )
        )
    elif turn.action == "verb":
        phases = run_turn_verb_phases(
            session,
            agent,
            area,
            turn,
            trigger_fired=trigger_fired,
        )
        if phases.path_move is not None:
            steps.append(
                _make_step(
                    "move",
                    turn.reasoning,
                    phases.path_move,
                    target=turn.target,
                )
            )
        verb_result = phases.outcome
        if isinstance(verb_result, str):
            outcome = ActionOutcome(result=verb_result, passive_result="")
        else:
            outcome = verb_result
        steps.append(
            _make_step(
                "verb",
                turn.reasoning,
                outcome,
                target=turn.target,
                content=turn.verb,
            )
        )

    return steps


def _pick_passive_from_steps(steps: list[TurnStep]) -> str:
    """Priority: interact > verb > emote > speak > look > move."""
    interact_passive = ""
    verb_passive = ""
    emote_passive = ""
    speak_passive = ""
    look_passive = ""
    move_passive = ""

    for step in steps:
        if not step.passive_result:
            continue
        if step.kind == "interact":
            interact_passive = step.passive_result
        elif step.kind == "verb":
            verb_passive = step.passive_result
        elif step.kind == "emote":
            emote_passive = step.passive_result
        elif step.kind == "speak":
            speak_passive = step.passive_result
        elif step.kind == "look":
            look_passive = step.passive_result
        elif step.kind == "move":
            move_passive = step.passive_result

    return (
        interact_passive
        or verb_passive
        or emote_passive
        or speak_passive
        or look_passive
        or move_passive
    )


def finalize_turn_record(
    turn: AgentCompoundTurn,
    nav_steps: list[TurnStep],
    action_steps: list[TurnStep],
    turn_number: int,
) -> TurnRecord:
    """Assemble a TurnRecord from completed sub-phases."""
    steps = nav_steps + action_steps
    return TurnRecord(
        turn_number=turn_number,
        steps=steps,
        result=_composite_result(steps),
        reasoning=turn.reasoning,
    )


def commit_turn_record(
    agent: Agent,
    record: TurnRecord,
    turn: AgentCompoundTurn,
    area: Area,
    *,
    session_turn: int | None = None,
    session: Session | None = None,
) -> TurnRecord:
    """Apply passive_result, memory, and last_action side effects."""
    passive = _pick_passive_from_steps(record.steps)
    if passive:
        agent.passive_result = passive

    # Prefer the agent's current area: transfer_agent / move_area may have moved
    # them mid-turn, leaving the turn-start ``area`` stale for nearby/witnesses.
    commit_area = area
    if session is not None:
        commit_area = session.get_area_for_agent(agent)

    agent.memory.record_turn(
        record,
        agent_id=agent.id,
        agent_name=agent.name,
        nearby_agents=tuple(
            (other.id, other.name) for other in commit_area.agents if other.id != agent.id
        ),
    )

    witness_session = session_turn if session_turn is not None else record.turn_number
    from campaign_rpg_engine.observations import broadcast_actor_turn

    broadcast_actor_turn(
        commit_area,
        agent,
        session_turn=witness_session,
        steps=record.steps,
    )

    agent.last_action = record.steps[-1].kind if record.steps else None
    if session is not None:
        session._emit_event(
            "turn_committed",
            agent=agent,
            area=commit_area,
            record=record,
            turn=turn,
        )
    return record


def run_compound_turn(
    agent: Agent,
    area: Area,
    turn: AgentCompoundTurn,
    turn_number: int,
    *,
    nav_steps: list[TurnStep] | None = None,
    session_turn: int | None = None,
    session: Session | None = None,
    source_area_id: str | None = None,
) -> TurnRecord:
    """
    Run a compound agent turn: move, then look/action.

    Pass ``nav_steps`` when navigation was already executed (e.g. debug step-nav).
    """
    if nav_steps is None:
        trigger_fired: set[tuple[str, str, str]] = set()
        nav_steps = execute_nav_phase(
            agent,
            area,
            turn,
            session=session,
            trigger_fired=trigger_fired,
        )
    else:
        trigger_fired = set()

    action_steps = execute_action_phase(
        agent,
        area,
        turn,
        session=session,
        source_area_id=source_area_id,
        trigger_fired=trigger_fired,
    )

    record = finalize_turn_record(turn, nav_steps, action_steps, turn_number)
    return commit_turn_record(agent, record, turn, area, session_turn=session_turn, session=session)


# Checklist name alias
step_agent_turn = run_compound_turn
