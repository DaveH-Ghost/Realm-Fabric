"""Shared text formatting for memory module render output."""

from __future__ import annotations

from src.memory_modules.base import WitnessedEvent
from src.turn_record import StepKind, TurnRecord, TurnStep

REASONING_WINDOW = 3

STEP_SALIENCE: dict[StepKind, int] = {
    "speak": 10,
    "interact": 7,
    "look": 3,
    "move": 1,
}

WITNESS_SALIENCE = STEP_SALIENCE["speak"]


def step_salience(kind: StepKind) -> int:
    return STEP_SALIENCE.get(kind, 0)


def should_include_reasoning(turn_index: int, total_turns: int) -> bool:
    """True when this stored turn is among the newest REASONING_WINDOW turns."""
    if total_turns <= 0:
        return False
    return turn_index >= total_turns - REASONING_WINDOW


def join_step_results(steps: list[TurnStep]) -> str:
    """Join step result lines in execution order."""
    parts = [step.result for step in steps if step.result.strip()]
    return "\n".join(parts)


def select_salient_steps(steps: list[TurnStep], *, in_recency_floor: bool) -> list[TurnStep]:
    """
    Pick which step results to include in a salient turn's Result line.

    Recency-floor turns keep all steps; older turns keep speak/interact only.
    """
    if in_recency_floor:
        return [step for step in steps if step.result.strip()]
    return [
        step
        for step in steps
        if step.result.strip() and step.kind in ("speak", "interact")
    ]


def format_own_turn(
    turn: TurnRecord,
    *,
    include_reasoning: bool = True,
    result_text: str | None = None,
) -> list[str]:
    lines = [f"Turn {turn.turn_number}:"]
    if include_reasoning and turn.reasoning:
        lines.append(f"Reasoning: {turn.reasoning}")
    result = turn.result if result_text is None else result_text
    if result.strip():
        lines.append(f"Result: {result}")
    return lines


def format_witnessed_events(events: list[WitnessedEvent], heading: str) -> list[str]:
    if not events:
        return []
    lines = [heading]
    for event in events:
        pos = f"at {event.actor_position}"
        lines.append(f"  - {event.text} ({event.actor_name} {pos})")
    return lines


def join_lines(lines: list[str]) -> str:
    return "\n".join(lines).rstrip()
