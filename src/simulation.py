"""
simulation.py

Compound turn execution for V0.2.5.

Pipeline per agent turn:
  optional move → optional look → optional speak → optional turn action (interact / emote)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.action_outcome import ActionOutcome
from src.actions import do_emote, do_interact, do_move, do_speak
from src.agent import Agent
from src.llm.schemas import AgentCompoundTurn
from src.memory import Memory, StepKind, TurnRecord, TurnStep
from src.perception import perform_look as do_look
from src.area import Area

if TYPE_CHECKING:
    from src.session import Session


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
    )


def execute_nav_phase(
    agent: Agent, area: Area, turn: AgentCompoundTurn
) -> list[TurnStep]:
    """Run optional move from compound turn. Commits position changes."""
    if not turn.move:
        return []

    outcome = do_move(agent, area, turn.move)
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
        outcome = do_interact(
            agent,
            area,
            turn.target or "",
            turn.verb or "",
            session=session,
            source_area_id=source_area_id,
        )
        steps.append(
            _make_step(
                "interact",
                turn.reasoning,
                outcome,
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

    return steps


def _pick_passive_from_steps(steps: list[TurnStep]) -> str:
    """Priority: interact > emote > speak > look > move."""
    interact_passive = ""
    emote_passive = ""
    speak_passive = ""
    look_passive = ""
    move_passive = ""

    for step in steps:
        if not step.passive_result:
            continue
        if step.kind == "interact":
            interact_passive = step.passive_result
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
) -> TurnRecord:
    """Apply passive_result, memory, and last_action side effects."""
    passive = _pick_passive_from_steps(record.steps)
    if passive:
        agent.passive_result = passive

    agent.memory.record_turn(record, agent_id=agent.id, agent_name=agent.name)

    witness_session = session_turn if session_turn is not None else record.turn_number
    from src.observations import broadcast_actor_turn

    broadcast_actor_turn(
        area,
        agent,
        session_turn=witness_session,
        steps=record.steps,
    )

    agent.last_action = record.steps[-1].kind if record.steps else None
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
        nav_steps = execute_nav_phase(agent, area, turn)

    action_steps = execute_action_phase(
        agent, area, turn, session=session, source_area_id=source_area_id
    )

    record = finalize_turn_record(turn, nav_steps, action_steps, turn_number)
    return commit_turn_record(
        agent, record, turn, area, session_turn=session_turn
    )


# Checklist name alias
step_agent_turn = run_compound_turn
