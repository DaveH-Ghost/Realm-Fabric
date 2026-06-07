"""
prompt.py

Two-phase prompt construction for V0.2 compound turns.
"""

from src.agent import Agent
from src.memory import TurnRecord
from src.perception import (
    build_passive_vision,
    get_available_interactions,
    get_available_look_targets,
)
from src.world import World


FEW_SHOT_NAV_EXAMPLES = """
Example 1: Move to a coordinate

Context:
You are at (1, 1).
You may move to any coordinate (x, y) where x and y are integers from 0 to 4.

Output:
{
  "reasoning": "The sign is at (2, 4). I will move closer.",
  "move_target": "2,3",
  "confidence": "decided",
  "emotion": "focused"
}

Example 2: Stay in place

Context:
You are at (2, 2).
You may move to any coordinate (x, y) where x and y are integers from 0 to 4.

Output:
{
  "reasoning": "I am already well positioned. I will stay and act from here.",
  "move_target": null,
  "confidence": "certain",
  "emotion": "calm"
}
""".strip()


FEW_SHOT_ACTION_EXAMPLES = """
Example 1: Look then speak

Context:
You are at (2, 3).
Ceramic Ball (obj_ball_01), (2, 2) - [?]
You can look at: obj_ball_01, obj_sign_01

Output:
{
  "reasoning": "I want to examine the ball and comment.",
  "look_target": "obj_ball_01",
  "turn_action": "speak",
  "target": null,
  "action_name": null,
  "content": "Interesting ball.",
  "confidence": "curious",
  "emotion": "intrigued"
}

Example 2: Speak only

Context:
You are at (1, 1).
You can look at: obj_ball_01, obj_sign_01

Output:
{
  "reasoning": "Nothing new to examine. I will speak.",
  "look_target": null,
  "turn_action": "speak",
  "target": null,
  "action_name": null,
  "content": "Hello, room.",
  "confidence": "certain",
  "emotion": "calm"
}
""".strip()


def _character_block(agent: Agent) -> str:
    return (
        f"You are {agent.name}.\n"
        f"Your personality: {agent.personality}\n\n"
        f"Your detailed description: {agent.description}"
    )


def _get_nav_system_instructions() -> str:
    return """You exist inside a small, controlled 5x5 grid room. Your coordinates range from (0,0) in the southwest corner to (4,4) in the northeast. Y increases northward.

This is the **navigation phase** of your turn. Decide whether to move before your action phase.

- move: Move to any in-bounds grid coordinate (x, y). Use move_target "x,y" (e.g. "2,3"), or null to stay.
- You cannot move outside the grid.

Always respond with a single, valid JSON object. Do not add any text before or after the JSON."""


def _get_action_system_instructions() -> str:
    return """You exist inside a small, controlled 5x5 grid room. Your coordinates range from (0,0) in the southwest corner to (4,4) in the northeast. Y increases northward.

This is the **action phase** of your turn (after any move). You may look at one entity, then take one turn action.

- look: Examine one entity from passive vision (optional; at most one look_target).
- speak: Say something out loud (turn_action "speak"; up to five sentences).
- interact: Use a listed object action (turn_action "interact" with target + action_name).
- turn_action "none": End after an optional look without speaking or interacting.

Important rules:
- Only entities in passive vision can be looked at (you do not see yourself).
- Hidden detail is marked "[?]"; stale examined knowledge is "[?] [changed]".
- Other agents show their most recent observable action on their vision line.
- Always respond with a single, valid JSON object. Do not add any text before or after the JSON."""


def _get_nav_move_block(agent: Agent) -> str:
    x, y = agent.position
    return (
        f"You are at ({x}, {y}).\n"
        "You may move to any coordinate (x, y) where x and y are integers from 0 to 4."
    )


def _format_interact_block(agent: Agent, world: World) -> str:
    interactions = get_available_interactions(agent, world)
    if not interactions:
        return ""
    lines = ["Object interactions available this turn:"]
    for action_name, obj_id, obj, action in interactions:
        if action.range == 0:
            range_label = "same tile"
        else:
            range_label = f"range {action.range}"
        lines.append(f"- {action_name} {obj_id} ({obj.name}) — {range_label}")
    return "\n".join(lines)


def _get_action_available_block(agent: Agent, world: World) -> str:
    targets = get_available_look_targets(agent, world)
    lines = []
    if targets:
        lines.append("You can look at: " + ", ".join(targets))
    else:
        lines.append("You can look at: (nothing visible to examine)")
    interact_block = _format_interact_block(agent, world)
    if interact_block:
        lines.append("")
        lines.append(interact_block)
    lines.append("")
    lines.append(
        'Turn action: set turn_action to "speak" (with content), "interact" '
        '(with target + action_name when available), or "none".'
    )
    return "\n".join(lines)


def _format_history(turns: list[TurnRecord]) -> str:
    if not turns:
        return "No previous turns yet."

    lines = []
    for t in turns:
        lines.append(f"Turn {t.turn_number}:")
        if t.nav_reasoning:
            lines.append(f"Navigation reasoning: {t.nav_reasoning}")
        if t.action_reasoning:
            lines.append(f"Action reasoning: {t.action_reasoning}")
        for step in t.steps:
            label = step.kind
            if step.target:
                label += f" → {step.target}"
            lines.append(f"  - {label}: {step.result}")
        lines.append(f"Result: {t.result}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _nav_output_format() -> str:
    return (
        "Respond with ONLY a valid JSON object matching this exact structure "
        "(no extra text, no markdown):\n"
        "{\n"
        '  "reasoning": "Your private navigation thoughts (max 400 characters).",\n'
        '  "move_target": "2,3" | null,\n'
        '  "confidence": "curious" | "certain" | ... (1-3 words),\n'
        '  "emotion": "focused" | "calm" | ... (1-3 words)\n'
        "}"
    )


def _action_output_format() -> str:
    return (
        "Respond with ONLY a valid JSON object matching this exact structure "
        "(no extra text, no markdown):\n"
        "{\n"
        '  "reasoning": "Your private action thoughts (max 400 characters).",\n'
        '  "look_target": "obj_ball_01" | null,\n'
        '  "turn_action": "speak" | "interact" | "none",\n'
        '  "target": "obj_cookie_01" | null,\n'
        '  "action_name": "eat" | null,\n'
        '  "content": "spoken text or null",\n'
        '  "confidence": "curious" | "certain" | ... (1-3 words),\n'
        '  "emotion": "focused" | "intrigued" | ... (1-3 words)\n'
        "}"
    )


def build_navigation_prompt(
    agent: Agent, world: World, include_examples: bool = False
) -> str:
    """Navigation-phase prompt (pre-turn vision + move rules)."""
    parts = [
        _character_block(agent),
        "",
        _get_nav_system_instructions(),
        "",
        world.get_room_description(),
        "",
        "Current situation:",
        build_passive_vision(agent, world),
        "",
        _get_nav_move_block(agent),
        "",
        "Recent history:",
        _format_history(agent.memory.get_recent_turns(10)),
        "",
        "Decide your move for this turn (or null to stay).",
        "",
        _nav_output_format(),
    ]
    if include_examples:
        parts.extend(["", "Here are navigation examples:", FEW_SHOT_NAV_EXAMPLES])
    return "\n".join(parts).strip()


def build_action_prompt(
    agent: Agent, world: World, include_examples: bool = False
) -> str:
    """Action-phase prompt (post-move vision + look + turn action)."""
    parts = [
        _character_block(agent),
        "",
        _get_action_system_instructions(),
        "",
        world.get_room_description(),
        "",
        "Current situation (after your move):",
        build_passive_vision(agent, world),
        "",
        _get_action_available_block(agent, world),
        "",
        "Recent history:",
        _format_history(agent.memory.get_recent_turns(10)),
        "",
        "You may speak up to five sentences. Spoken text should be things you say out loud.",
        "",
        _action_output_format(),
    ]
    if include_examples:
        parts.extend(["", "Here are action-phase examples:", FEW_SHOT_ACTION_EXAMPLES])
    return "\n".join(parts).strip()


def build_prompt(agent: Agent, world: World, include_examples: bool = False) -> str:
    """Backward-compatible alias: returns the navigation prompt."""
    return build_navigation_prompt(agent, world, include_examples=include_examples)
