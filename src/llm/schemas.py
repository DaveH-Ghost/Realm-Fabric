"""
AgentTurn Schema - Version 0 (Authoritative Source)

This is the canonical Pydantic schema for agent turn outputs in Version 0.

IMPORTANT:
- This file (src/llm/schemas.py) is the single source of truth.
- The simulation code will import from here.
- The copy in docs/schemas/AgentTurn.py is kept only as a design reference.

Current V0 Scope:
- Only three actions: move, look, speak
- Max 3 sentences + 280 character limit for speak content
- Lightweight pure-dialogue heuristic (rejects obvious emotes/actions)
- `reasoning` limited to 400 characters (supports prompt token budget)
- move target uses full direction strings ("north", "east", etc.)
- confidence and emotion fields are kept for now (can be removed later if problematic)

Last synced from design docs: 2026-05-31
"""

from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional
import re


ActionType = Literal[
    "move",
    "look",
    "speak",
]


class AgentTurn(BaseModel):
    """
    The structured output of one agent's turn.

    Design notes for V0:
    - `reasoning` is always required and private (never shown to other agents).
      Limited to 400 characters.
    - `target` is kept as a string for simplicity (with format rules per action).
    - `content` (for speak) is limited to a maximum of 3 sentences and 280 characters.
    - All text in `content` is treated as verbal dialogue only (lightweight heuristic enforcement).
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
            "- look: Use the object ID (e.g. 'obj_ball_01' or 'obj_sign_01')\n"
            "- speak: Leave empty (not used)"
        )
    )

    content: Optional[str] = Field(
        default=None,
        description="Only used with the 'speak' action. Maximum 3 sentences of pure dialogue."
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
    # - Sentence counting and pure-dialogue checks are intentionally lightweight heuristics.
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

        # Lightweight pure-dialogue heuristic for V0
        # NOTE: This heuristic is known to have false positives on legitimate dialogue
        # that uses parentheses (e.g. "I wonder what (the sign) says"). This is an
        # accepted limitation for V0. See "Known Limitations (V0)" in the checklist.
        if any(c in text for c in "*_") or ("(" in text and ")" in text):
            # Catches common emote/action patterns: *smiles*, _waves_, (laughs quietly), etc.
            raise ValueError(
                "ERR:INVALID_CONTENT: speak content must be pure verbal dialogue. "
                "Emotes, actions, or descriptions using asterisks, underscores, or parentheses are not allowed."
            )

        # Improved sentence counting (handles ellipses and multiple punctuation better than before)
        sentences = [s.strip() for s in re.split(r"[.!?]+\s*", text) if s.strip()]
        sentence_count = len(sentences)

        if sentence_count > 3:
            raise ValueError(
                f"ERR:CONTENT_TOO_LONG: speak is limited to a maximum of 3 sentences "
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
