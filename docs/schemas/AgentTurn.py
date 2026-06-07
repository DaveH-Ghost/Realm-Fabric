"""
AgentTurn Schema - V0 / V0.1 (Design Reference)

!!! IMPORTANT !!!

This file is NO LONGER the authoritative version for new work.

The real V0.1 implementation lives here:
    src/llm/schemas.py

**V0.2** replaces single-action `AgentTurn` on the LLM path with
`AgentNavigationTurn` + `AgentActionTurn` (implemented in `src/llm/schemas.py`;
see docs/schemas/ and v0.2-implementation-readiness-checklist.md). This file
remains a snapshot of the pre-V0.2 one-action-per-call model.

For current runtime imports (until v0.2.0 ships), use:
    from src.llm.schemas import AgentTurn

Current V0.1 Scope (superseded by V0.2 when shipped):
- Only three actions: move, look, speak
- Max 5 sentences + 280 character limit for speak content
- Pure dialogue encouraged via prompt only (no runtime emote/action detection)
- `reasoning` limited to 400 characters (supports prompt token budget)
- move target uses full direction strings ("north", "east", etc.)
- confidence and emotion fields are kept for now (can be removed later if problematic)

Last synced: 2026-06-05 (V0.2 prep — marked pre-V0.2; runtime still V0.1)
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
    - `confidence` and `emotion` are optional and kept short (max 3 words).
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

    confidence: Optional[str] = Field(
        default=None,
        description="How confident you feel about this decision. Use 1-3 words max (e.g. 'certain', 'hesitant', 'curious')."
    )

    emotion: Optional[str] = Field(
        default=None,
        description="Your current dominant feeling. Use 1-3 words max (e.g. 'curious', 'uneasy', 'amused')."
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

    @field_validator("confidence", "emotion")
    @classmethod
    def validate_short_fields(cls, v: Optional[str]):
        if v is None:
            return v

        word_count = len(v.strip().split())

        if word_count > 3:
            raise ValueError("ERR:INVALID_CONTENT: confidence and emotion should be short (1-3 words max).")

        return v
