"""Shared turn and witness render helpers for memory modules."""

from __future__ import annotations

from src.memory_modules.base import WitnessedEvent
from src.area_event import AREA_EVENT_ACTOR_ID
from src.turn_record import TurnRecord, TurnStep

REASONING_WINDOW = 3


def should_include_reasoning(turn_index: int, total_turns: int) -> bool:
    """True when this stored turn is among the newest REASONING_WINDOW turns."""
    if total_turns <= 0:
        return False
    return turn_index >= total_turns - REASONING_WINDOW


def join_step_results(steps: list[TurnStep]) -> str:
    """Join step result lines in execution order."""
    parts = [step.result for step in steps if step.result.strip()]
    return "\n".join(parts)


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
        if event.actor_id == AREA_EVENT_ACTOR_ID:
            lines.append(f"  - {event.text}")
        else:
            pos = f"at {event.actor_position}"
            lines.append(f"  - {event.text} ({event.actor_name} {pos})")
    return lines


def format_stored_turns_block(
    turns: list[TurnRecord],
    witnessed_before: list[list[WitnessedEvent]],
    pending: list[WitnessedEvent],
) -> list[str]:
    """Render own turns plus witness gaps (recent_turns / rolling_summary detail section)."""
    if not turns and not pending:
        return []

    lines: list[str] = []
    total = len(turns)
    for index, turn in enumerate(turns):
        witnessed = witnessed_before[index] if index < len(witnessed_before) else []
        if witnessed:
            lines.extend(
                format_witnessed_events(
                    witnessed,
                    f"Before turn {turn.turn_number}, you observed:",
                )
            )
            lines.append("")
        lines.extend(
            format_own_turn(
                turn,
                include_reasoning=should_include_reasoning(index, total),
            )
        )
        lines.append("")

    if pending:
        if turns:
            heading = f"Since turn {turns[-1].turn_number}, you observed:"
        else:
            heading = "You observed:"
        lines.extend(format_witnessed_events(pending, heading))

    return lines


def join_lines(lines: list[str]) -> str:
    return "\n".join(lines).rstrip()
