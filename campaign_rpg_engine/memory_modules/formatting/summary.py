"""Full-fidelity turn blocks for rolling-summary LLM consolidation."""

from __future__ import annotations

from campaign_rpg_engine.memory_modules.base import WitnessedEvent
from campaign_rpg_engine.memory_modules.formatting.common import (
    format_own_turn,
    format_witnessed_events,
    join_lines,
)
from campaign_rpg_engine.turn_record import TurnRecord


def format_turns_batch_for_summary(
    turns: list[TurnRecord],
    witnessed_before: list[list[WitnessedEvent]],
) -> str:
    """Full-fidelity turn block for the summary LLM (includes all reasoning)."""
    lines: list[str] = []
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
        lines.extend(format_own_turn(turn, include_reasoning=True))
        lines.append("")
    return join_lines(lines)
