"""Shared turn and witness render helpers for memory modules."""

from __future__ import annotations

from campaign_rpg_engine.area_event import AREA_EVENT_ACTOR_ID
from campaign_rpg_engine.memory_modules.base import WitnessedEvent
from campaign_rpg_engine.turn_record import TurnRecord, TurnStep

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
        heading = f"Since turn {turns[-1].turn_number}, you observed:" if turns else "You observed:"
        lines.extend(format_witnessed_events(pending, heading))

    return lines


def join_lines(lines: list[str]) -> str:
    return "\n".join(lines).rstrip()


# Display names that collide with memory batch headings / second-person results
# ("Turn 3:", "Reasoning:", "You said:…"). Skip these for mention matching.
RESERVED_MENTION_NAMES = frozenset(
    {"you", "turn", "before", "reasoning", "result", "observed", "since"}
)


def is_reserved_mention_name(name: str) -> bool:
    """True when ``name`` should never count as an in-window name mention."""
    return name.strip().lower() in RESERVED_MENTION_NAMES


def corpus_for_name_matching(
    turns: list[TurnRecord],
    witnessed_before: list[list[WitnessedEvent]],
    *,
    pending: list[WitnessedEvent] | None = None,
) -> str:
    """
    Text where agent name mentions are searched.

    Uses turn bodies and witness event text only — not render headings like
    ``Turn N:`` / ``Reasoning:`` / ``Before turn…`` that would false-match.
    """
    parts: list[str] = []
    for index, turn in enumerate(turns):
        witnessed = witnessed_before[index] if index < len(witnessed_before) else []
        for event in witnessed:
            if event.text.strip():
                parts.append(event.text)
        if turn.reasoning.strip():
            parts.append(turn.reasoning)
        if turn.result.strip():
            parts.append(turn.result)
        for step in turn.steps:
            for value in (step.target, step.content, step.result, step.passive_result):
                if value and str(value).strip():
                    parts.append(str(value))
    for event in pending or ():
        if event.text.strip():
            parts.append(event.text)
    return "\n".join(parts)
