"""
prompt.py

Prompt construction for Version 0.

This module builds the full text prompt sent to the LLM (DeepSeek via OpenRouter).

It follows the exact structure and rules agreed in the readiness checklist (Section 7).

The prompt includes:
- Character description
- System rules
- Room description
- Current passive vision (from perception)
- Available actions this turn (computed from world state)
- Recent history (from agent's memory)
- Turn-specific reminders
- Output format reminder
- 4 few-shot examples (optional; off by default for token efficiency)

This is kept separate from the LLM client so it can be tested and iterated independently.
"""

from src.agent import Agent
from src.memory import TurnRecord
from src.perception import build_passive_vision
from src.world import World


# =============================================================================
# Few-shot examples (copied verbatim from the readiness checklist)
# =============================================================================

FEW_SHOT_EXAMPLES = """
Example 1: Correct use of `speak` (pure dialogue only)

Context:
You are at (1, 1).
Ceramic Ball (obj_ball_01), (2, 2) - [?]
Wooden Sign (obj_sign_01), (2, 4) - A simple wooden sign. It reads: "This is a controlled environment..."
You can move in the following directions this turn:
- north
- east
- south
- west
You can look at anything with the [?] tag.

Output:
{
  "reasoning": "I notice the ball has a [?] tag. I should comment on that and consider looking at it soon.",
  "action": "speak",
  "target": null,
  "content": "That ball has a question mark next to it. I wonder what happens if I look at it.",
  "confidence": "curious",
  "emotion": "intrigued"
}

Example 2: Using `look` when seeing `[?]` 

Context:
You are at (2, 3).
Ceramic Ball (obj_ball_01), (2, 2) - A slightly worn ceramic ball. It has a few scuffs and feels light.
Wooden Sign (obj_sign_01), (2, 4) - [?]
You can move in the following directions this turn:
- north
- east
- south
- west
You can look at anything with the [?] tag.

Output:
{
  "reasoning": "The wooden sign shows [?], which means I haven't properly examined it yet. I should look at it to get the current information.",
  "action": "look",
  "target": "obj_sign_01",
  "content": null,
  "confidence": "decided",
  "emotion": "curious"
}

Example 3: Choosing a valid `move` direction

Context:
You are at (2, 2).
Ceramic Ball (obj_ball_01), (2, 2) - A slightly worn ceramic ball. It has a few scuffs and feels light.
Wooden Sign (obj_sign_01), (2, 4) - A simple wooden sign. It reads: "..."
You can move in the following directions this turn:
- north
- east
- south
- west

Output:
{
  "reasoning": "I want to get closer to the sign so I can examine it more easily. Moving north is the most direct option.",
  "action": "move",
  "target": "north",
  "content": null,
  "confidence": "certain",
  "emotion": "focused"
}

Example 4: Responding to the sign being updated

Context:
You are at (1, 1).
Ceramic Ball (obj_ball_01), (2, 2) - A slightly worn ceramic ball. It has a few scuffs and feels light.
Wooden Sign (obj_sign_01), (2, 4) - [?] The wooden sign has changed since you last looked at it.
You can move in the following directions this turn:
- north
- east
- south
- west
You can look at anything with the [?] tag.

Output:
{
  "reasoning": "The sign now shows that it has changed since I last looked at it. I should examine it again to see the new message.",
  "action": "look",
  "target": "obj_sign_01",
  "content": null,
  "confidence": "curious",
  "emotion": "alert"
}
""".strip()


# =============================================================================
# Prompt sections
# =============================================================================

def _get_system_instructions() -> str:
    """Core rules of the simulation (compiled from the V0 spec)."""
    return """You exist inside a small, controlled 5x5 grid room. Your coordinates range from (0,0) in the southwest corner to (4,4) in the northeast. Y increases northward.

You may only perform ONE action per turn. The allowed actions are:
- move: Move exactly one tile in a cardinal direction (north, east, south, or west). You cannot move outside the grid.
- look: Examine an object that currently appears in your passive vision (including objects marked with [?]). You will receive its full description.
- speak: Say something out loud. Limited to a maximum of three sentences. All text must be pure verbal dialogue. Do not include emotes (*smiles*), actions (_waves_), or parenthetical descriptions.

Important rules:
- Only objects listed in your current passive vision can be looked at.
- Objects you have not examined (or that have changed since you last looked) appear with "[?]" instead of their description.
- Your words when speaking have no direct mechanical effect on the world, but they are recorded and may influence how the environment responds over time (for example, the text on the wooden sign may be updated based on what you say).
- Always respond with a single, valid JSON object. Do not add any text before or after the JSON."""


def _get_available_actions(agent: Agent, world: World) -> str:
    """Build the exact 'Available Actions This Turn' block per the spec."""
    x, y = agent.position
    directions = ["north", "east", "south", "west"]
    deltas = {
        "north": (0, 1),
        "east": (1, 0),
        "south": (0, -1),
        "west": (-1, 0),
    }

    legal = []
    for d in directions:
        dx, dy = deltas[d]
        if world.is_valid_position((x + dx, y + dy)):
            legal.append(d)

    lines = []
    if legal:
        lines.append("You can move in the following directions this turn:")
        for d in legal:
            lines.append(f"- {d}")
        lines.append("")

    lines.append("You can look at anything with the [?] tag.")

    return "\n".join(lines)


def _format_history(turns: list[TurnRecord]) -> str:
    """Format the recent history exactly as specified in the checklist."""
    if not turns:
        return "No previous turns yet."

    lines = []
    for t in turns:  # oldest first
        lines.append(f"Turn {t.turn_number}:")
        lines.append(f"Action: {t.action}")
        if t.target is not None:
            lines.append(f"Target: {t.target}")
        lines.append(f"Reasoning: {t.reasoning}")
        lines.append(f"Result: {t.result}")
        lines.append("")  # blank line between turns

    return "\n".join(lines).rstrip()


def build_prompt(agent: Agent, world: World, include_examples: bool = False) -> str:
    """
    Assemble the complete prompt for the current turn.

    This follows the canonical high-level order from the V0 spec:
    Character Description, System Instructions, Room Description,
    Current Passive Vision, Available Actions, Recent History,
    Current Instructions, Output Format.

    The four few-shot examples from the checklist are included only when
    include_examples=True (off by default for token efficiency; current
    models perform well without them).

    Args:
        include_examples: Whether to include the four few-shot examples.
            Default is False.
    """
    parts = []

    # 1. Character Description
    parts.append(f"You are {agent.name}.")
    parts.append(agent.description)
    parts.append("")

    # 2. System Instructions / Rules
    parts.append(_get_system_instructions())
    parts.append("")

    # 3. Room Description
    parts.append(world.get_room_description())
    parts.append("")

    # 4. Current Passive Vision
    parts.append("Current situation:")
    parts.append(build_passive_vision(agent, world))
    parts.append("")

    # 5. Available Actions This Turn
    parts.append(_get_available_actions(agent, world))
    parts.append("")

    # 6. Recent History
    history_text = _format_history(agent.memory.get_recent_turns(10))
    parts.append("Recent history:")
    parts.append(history_text)
    parts.append("")

    # 7. Current Instructions / Reminders
    parts.append("You may only speak up to three sentences this turn. All spoken text must be pure verbal dialogue.")
    parts.append("")

    # 8. Output Format
    parts.append(
        "Respond with ONLY a valid JSON object matching this exact structure (no extra text, no markdown):\n"
        "{\n"
        '  "reasoning": "Your private thoughts (max 400 characters).",\n'
        '  "action": "move" | "look" | "speak",\n'
        '  "target": "north" | "obj_ball_01" | null,\n'
        '  "content": "spoken text or null",\n'
        '  "confidence": "curious" | "certain" | ... (1-3 words),\n'
        '  "emotion": "focused" | "intrigued" | ... (1-3 words)\n'
        "}"
    )
    parts.append("")

    # Few-shot examples (optional for token savings / future chat format)
    if include_examples:
        parts.append("Here are some examples of correct behavior:")
        parts.append(FEW_SHOT_EXAMPLES)

    return "\n".join(parts).strip()
