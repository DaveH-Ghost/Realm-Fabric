"""
prompt.py

Single-call prompt construction for V0.2.5 compound turns.
"""

from src.agent import Agent
from src.perception import (
    build_passive_vision,
    get_available_interactions,
    get_available_look_targets,
)
from src.world import World


FEW_SHOT_COMPOUND_EXAMPLES = """
Example 1: Move, look, and speak

Context:
You are at (1, 1).
Ceramic Ball (obj_ball_01), (2, 2) - [?]
You can look at: obj_ball_01, obj_sign_01

Output:
{
  "reasoning": "The ball is at (2, 2). I will move closer, examine it, and comment.",
  "move_target": "2,3",
  "look_target": "obj_ball_01",
  "turn_action": "speak",
  "target": null,
  "action_name": null,
  "content": "Interesting ball.",
  "confidence": "curious",
  "emotion": "intrigued"
}

Example 2: Stay in place and speak

Context:
You are at (2, 2).
You can look at: obj_ball_01, obj_sign_01

Output:
{
  "reasoning": "Nothing new to examine. I will speak from here.",
  "move_target": null,
  "look_target": null,
  "turn_action": "speak",
  "target": null,
  "action_name": null,
  "content": "Hello, room.",
  "confidence": "certain",
  "emotion": "calm"
}

Example 3: Move only

Context:
You are at (1, 1).
You may move to any coordinate (x, y) where x and y are integers from 0 to 4.

Output:
{
  "reasoning": "The sign is at (2, 4). I will move closer.",
  "move_target": "2,3",
  "look_target": null,
  "turn_action": "none",
  "target": null,
  "action_name": null,
  "content": null,
  "confidence": "decided",
  "emotion": "focused"
}
""".strip()


def _character_block(agent: Agent) -> str:
    return (
        f"You are {agent.name}.\n"
        f"Your personality: {agent.personality}\n\n"
        f"Your detailed description: {agent.description}"
    )


def _get_compound_system_instructions() -> str:
    return """You exist inside a small, controlled 5x5 grid room. Your coordinates range from (0,0) in the southwest corner to (4,4) in the northeast. Y increases northward.

Each turn you may plan a **compound turn** executed in this order:
1. **Move** (optional): move to any in-bounds grid coordinate (x, y), or stay (move_target null).
2. **Look** (optional): examine one entity from passive vision (at most one look_target).
3. **Turn action** (optional): speak, interact with a listed object action, or none.

Important rules:
- You plan from your **current** position and vision. Your move runs first; look and turn action happen **after** that move.
- Only pick look/interact targets you expect to be valid after moving.
- move: use move_target "x,y" (e.g. "2,3"), or null to stay. You cannot move outside the grid.
- look: optional; a list of objects you can look at will be provided.
- Hidden detail is marked "[?]"; stale examined knowledge is "[?] [changed]".
- Other agents show their most recent observable action on their vision line.
- speak: up to five sentences when turn_action is "speak".
- interact: turn_action "interact" with target object id + action_name when listed below.
- turn_action "none": end after optional move/look without speaking or interacting.

Always respond with a single, valid JSON object. Do not add any text before or after the JSON."""


def _get_move_block(agent: Agent) -> str:
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


def _get_available_block(agent: Agent, world: World) -> str:
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


def _compound_output_format() -> str:
    return (
        "Respond with ONLY a valid JSON object matching this exact structure "
        "(no extra text, no markdown):\n"
        "{\n"
        '  "reasoning": "Your private thoughts for the full turn (max 400 characters).",\n'
        '  "move_target": "2,3" | null,\n'
        '  "look_target": "obj_ball_01" | null,\n'
        '  "turn_action": "speak" | "interact" | "none",\n'
        '  "target": "obj_cookie_01" | null,\n'
        '  "action_name": "eat" | null,\n'
        '  "content": "spoken text or null",\n'
        '  "confidence": "curious" | "certain" | ... (1-3 words),\n'
        '  "emotion": "focused" | "calm" | ... (1-3 words)\n'
        "}"
    )


def build_compound_prompt(
    agent: Agent, world: World, include_examples: bool = False
) -> str:
    """Build the single LLM prompt for one compound agent turn."""
    parts = [
        _character_block(agent),
        "",
        _get_compound_system_instructions(),
        "",
        world.get_room_description(),
        "",
        "Current situation:",
        build_passive_vision(agent, world),
        "",
        _get_move_block(agent),
        "",
        _get_available_block(agent, world),
        "",
        "Memory:",
        agent.memory.render_prompt_block(agent, world),
        "",
        "Plan your full compound turn (move, then look, then turn action).",
        "",
        "You may speak up to five sentences. Spoken text should be things you say out loud.",
        "",
        _compound_output_format(),
    ]
    if include_examples:
        parts.extend(["", "Here are compound turn examples:", FEW_SHOT_COMPOUND_EXAMPLES])
    return "\n".join(parts).strip()


def build_prompt(agent: Agent, world: World, include_examples: bool = False) -> str:
    """Alias for the compound turn prompt."""
    return build_compound_prompt(agent, world, include_examples=include_examples)
