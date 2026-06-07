"""
simulation.py

Compound turn execution for V0.2.

Pipeline per agent turn:
  navigation (optional move) → action phase (optional look → optional turn action)
"""

from src.action_outcome import ActionOutcome
from src.actions import do_interact, do_move, do_speak
from src.agent import Agent
from src.llm.schemas import AgentActionTurn, AgentNavigationTurn
from src.memory import StepKind, TurnRecord, TurnStep
from src.perception import perform_look as do_look
from src.world import World


def next_turn_number_for_agent(agent: Agent) -> int:
    """Return the next per-agent sequential turn number for TurnRecord."""
    return agent.memory.turn_count + 1


def _append_passive_mood(passive_result: str, action_turn: AgentActionTurn | None) -> str:
    """Append confidence/emotion from the action phase to passive_result."""
    if not passive_result or action_turn is None:
        return passive_result

    parts = []
    if action_turn.confidence:
        parts.append(f"confidence: {action_turn.confidence}")
    if action_turn.emotion:
        parts.append(f"Emotion: {action_turn.emotion}")
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


def execute_nav_phase(agent: Agent, world: World, nav_turn: AgentNavigationTurn) -> list[TurnStep]:
    """Run optional move from navigation phase. Commits position changes."""
    if not nav_turn.move_target:
        return []

    outcome = do_move(agent, world, nav_turn.move_target)
    return [
        _make_step(
            "move",
            nav_turn.reasoning,
            outcome,
            target=nav_turn.move_target,
        )
    ]


def execute_action_phase(
    agent: Agent, world: World, action_turn: AgentActionTurn
) -> list[TurnStep]:
    """Run optional look and turn action from action phase."""
    steps: list[TurnStep] = []

    if action_turn.look_target:
        outcome = do_look(agent, world, action_turn.look_target)
        steps.append(
            _make_step(
                "look",
                action_turn.reasoning,
                outcome,
                target=action_turn.look_target,
            )
        )

    if action_turn.turn_action == "speak":
        outcome = do_speak(agent, world, action_turn.content or "")
        steps.append(
            _make_step(
                "speak",
                action_turn.reasoning,
                outcome,
                content=action_turn.content,
            )
        )
    elif action_turn.turn_action == "interact":
        outcome = do_interact(
            agent,
            world,
            action_turn.target or "",
            action_turn.action_name or "",
        )
        steps.append(
            _make_step(
                "interact",
                action_turn.reasoning,
                outcome,
                target=action_turn.target,
                content=action_turn.action_name,
            )
        )

    return steps


def _pick_passive_from_steps(
    steps: list[TurnStep], action_turn: AgentActionTurn | None
) -> str:
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
    return _append_passive_mood(winner, action_turn)


def finalize_turn_record(
    nav_turn: AgentNavigationTurn,
    action_turn: AgentActionTurn | None,
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
        nav_reasoning=nav_turn.reasoning,
        action_reasoning=action_turn.reasoning if action_turn else "",
    )


def commit_turn_record(
    agent: Agent,
    record: TurnRecord,
    action_turn: AgentActionTurn | None,
) -> TurnRecord:
    """Apply passive_result, memory, and last_action side effects."""
    passive = _pick_passive_from_steps(record.steps, action_turn)
    if passive:
        agent.passive_result = passive

    agent.memory.add_turn(record)
    agent.last_action = record.steps[-1].kind if record.steps else None
    return record


def run_compound_turn(
    agent: Agent,
    world: World,
    nav_turn: AgentNavigationTurn,
    action_turn: AgentActionTurn | None,
    turn_number: int,
    *,
    nav_steps: list[TurnStep] | None = None,
) -> TurnRecord:
    """
    Run a compound agent turn: navigation then action phase.

    Pass ``nav_steps`` when navigation was already executed (LLM path runs move
    before the action LLM so the action prompt sees post-move vision). When
    ``action_turn`` is None, records a partial turn with navigation steps only.
    """
    if nav_steps is None:
        nav_steps = execute_nav_phase(agent, world, nav_turn)

    action_steps: list[TurnStep] = []
    if action_turn is not None:
        action_steps = execute_action_phase(agent, world, action_turn)

    record = finalize_turn_record(
        nav_turn, action_turn, nav_steps, action_steps, turn_number
    )
    return commit_turn_record(agent, record, action_turn)


# Checklist name alias
step_agent_turn = run_compound_turn
