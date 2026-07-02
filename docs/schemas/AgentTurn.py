"""
AgentTurn Schema — HISTORICAL (V0 / V0.1)

!!! SUPERSEDED — DO NOT USE FOR NEW WORK !!!

Current schema: **AgentCompoundTurn** — see [README.md](README.md) and
`src/llm/schemas.py` / `from realm_fabric import AgentCompoundTurn`.

This file snapshots the pre-V0.2 **one-action-per-call** model (move | look | speak).
Removed from the runtime LLM path in V0.2; fully replaced by compound turns in V0.2.5.

Kept for archaeology and links from old readiness checklists.

Last synced: 2026-06-05 (marked historical)
"""

from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional
import re


ActionType = Literal[
    "move",
    "look",
    "speak",
]

MAX_SPEAK_SENTENCES = 5


def count_speak_sentences(text: str) -> int:
    """Count sentences; runs of 2+ periods are ellipses, not boundaries."""
    normalized = re.sub(r"\.{2,}", "\u2026", text.strip())
    parts = [s.strip() for s in re.split(r"[.!?]+\s*", normalized) if s.strip()]
    return len(parts)


class AgentTurn(BaseModel):
    """
    The structured output of one agent's turn.

    Design notes for V0:
    - `reasoning` is always required and private (never shown to other agents).
      Limited to 400 characters.
    - `target` is kept as a string for simplicity (with format rules per action).
    - `content` (for speak) is limited to a maximum of 5 sentences and 280 characters.
    - All text in `content` is treated as verbal dialogue (enforced by prompt, not runtime parsing).
    """

    reasoning: str = Field(
        description=(
            "Your private internal thoughts. This is NOT visible to other agents. "
            "Use this to stay in character, reflect on the situation, and decide your action."
        )
    )

    action: ActionType = Field(
        description="The single action you will perform this turn. Only one action allowed."
    )

    target: Optional[str] = Field(
        default=None,
        description=(
            "What the action is directed toward.\n"
            "Rules by action:\n"
            "- move: Must be a full direction string: 'north', 'east', 'south', or 'west'\n"
            "- look: Use the entity ID (e.g. 'obj_ball_01', 'obj_sign_01', or 'agent_goblin_01')\n"
            "- speak: Leave empty (not used)"
        )
    )

    content: Optional[str] = Field(
        default=None,
        description="Only used with the 'speak' action. Maximum 5 sentences of pure dialogue."
    )

    # =====================
    # Validators
    # =====================

    # NOTE ON VALIDATION SCOPE (V0)
    # - This model performs structural validation + basic content guardrails only.
    # - Runtime validation (e.g. "is the 'look' target currently visible in passive vision?")
    #   is the responsibility of the action execution layer, not this Pydantic model.
    # - Sentence counting is an intentionally lightweight heuristic.
    # - A new error code (REASONING_TOO_LONG) has been added to support token budget control.

    @field_validator("reasoning")
    @classmethod
    def validate_reasoning_length(cls, v: str):
        text = v.strip()
        if len(text) > 400:
            raise ValueError(
                "ERR:REASONING_TOO_LONG: reasoning must be 400 characters or fewer "
                f"(current length: {len(text)})."
            )
        return v

    @field_validator("target")
    @classmethod
    def validate_target(cls, v: Optional[str], info):
        if v is None:
            return v

        action = info.data.get("action")

        if action == "move" and v:
            valid_directions = {"north", "east", "south", "west"}
            if v.strip().lower() not in valid_directions:
                raise ValueError(
                    "ERR:INVALID_TARGET: For 'move', target must be one of: north, east, south, west"
                )

        return v

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: Optional[str], info):
        if v is None:
            return v

        action = info.data.get("action")
        if action != "speak":
            return v

        text = v.strip()
        if not text:
            return v

        sentence_count = count_speak_sentences(text)

        if sentence_count > MAX_SPEAK_SENTENCES:
            raise ValueError(
                f"ERR:CONTENT_TOO_LONG: speak is limited to a maximum of 5 sentences "
                f"in V0 (you used {sentence_count})."
            )

        # Hard character safety limit (supports overall prompt token budget targets)
        if len(text) > 280:
            raise ValueError(
                f"ERR:CONTENT_TOO_LONG: speak content is limited to 280 characters "
                f"in V0 (you used {len(text)})."
            )

        return v
