"""
simulation.py

Compound turn execution for V0.2.5.

Pipeline per agent turn:
  optional move → optional look → optional turn action (speak / interact)
"""

from src.action_outcome import ActionOutcome
from src.actions import do_interact, do_move, do_speak
from src.agent import Agent
from src.llm.schemas import AgentCompoundTurn
from src.memory import Memory, StepKind, TurnRecord, TurnStep
from src.perception import perform_look as do_look
from src.area import Area


def next_turn_number_for_agent(agent: Agent) -> int:
    """Return the next per-agent sequential turn number for TurnRecord."""
    return agent.memory.turn_count + 1


def _append_passive_mood(passive_result: str, turn: AgentCompoundTurn) -> str:
    """Append confidence/emotion from the turn to passive_result."""
    if not passive_result:
        return passive_result

    parts = []
    if turn.confidence:
        parts.append(f"confidence: {turn.confidence}")
    if turn.emotion:
        parts.append(f"Emotion: {turn.emotion}")
    if not parts:
        return passive_result

    return f"{passive_result} ({', '.join(parts)})"


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
    if not turn.move_target:
        return []

    outcome = do_move(agent, area, turn.move_target)
    return [
        _make_step(
            "move",
            turn.reasoning,
            outcome,
            target=turn.move_target,
        )
    ]


def execute_action_phase(
    agent: Agent, area: Area, turn: AgentCompoundTurn
) -> list[TurnStep]:
    """Run optional look and turn action from compound turn."""
    steps: list[TurnStep] = []

    if turn.look_target:
        outcome = do_look(agent, area, turn.look_target)
        steps.append(
            _make_step(
                "look",
                turn.reasoning,
                outcome,
                target=turn.look_target,
            )
        )

    if turn.turn_action == "speak":
        outcome = do_speak(agent, area, turn.content or "")
        steps.append(
            _make_step(
                "speak",
                turn.reasoning,
                outcome,
                content=turn.content,
            )
        )
    elif turn.turn_action == "interact":
        outcome = do_interact(
            agent,
            area,
            turn.target or "",
            turn.action_name or "",
        )
        steps.append(
            _make_step(
                "interact",
                turn.reasoning,
                outcome,
                target=turn.target,
                content=turn.action_name,
            )
        )

    return steps


def _pick_passive_from_steps(steps: list[TurnStep], turn: AgentCompoundTurn) -> str:
    """Priority: turn action > look > move."""
    turn_action_passive = ""
    look_passive = ""
    move_passive = ""

    for step in steps:
        if not step.passive_result:
            continue
        if step.kind in ("speak", "interact"):
            turn_action_passive = step.passive_result
        elif step.kind == "look":
            look_passive = step.passive_result
        elif step.kind == "move":
            move_passive = step.passive_result

    winner = turn_action_passive or look_passive or move_passive
    return _append_passive_mood(winner, turn)


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
    passive = _pick_passive_from_steps(record.steps, turn)
    if passive:
        agent.passive_result = passive

    agent.memory.record_turn(record, agent_id=agent.id, agent_name=agent.name)

    witness_session = session_turn if session_turn is not None else record.turn_number
    from src.observations import broadcast_actor_turn

    broadcast_actor_turn(area, agent, session_turn=witness_session)

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
) -> TurnRecord:
    """
    Run a compound agent turn: move, then look/action.

    Pass ``nav_steps`` when navigation was already executed (e.g. debug step-nav).
    """
    if nav_steps is None:
        nav_steps = execute_nav_phase(agent, area, turn)

    action_steps = execute_action_phase(agent, area, turn)

    record = finalize_turn_record(turn, nav_steps, action_steps, turn_number)
    return commit_turn_record(
        agent, record, turn, area, session_turn=session_turn
    )


# Checklist name alias
step_agent_turn = run_compound_turn
