"""Area-wide narrator/GM events visible to all agents in an area."""

from __future__ import annotations

from dataclasses import dataclass

# WitnessedEvent pseudo-actor for memory ingest (not a real agent).
AREA_EVENT_ACTOR_ID = "__area__"
AREA_EVENT_ACTOR_NAME = "Environment"

DEFAULT_MAX_RECENT_AREA_EVENTS = 5


@dataclass(frozen=True)
class AreaEventRecord:
    """One room-wide event stored on the area and shown in passive vision."""

    session_turn: int
    text: str


def parse_area_event_arg(arg: str) -> str:
    """Parse ``emit-event`` CLI argument (quoted or plain text)."""
    text = arg.strip()
    if not text:
        return ""
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1].strip()
    return text
