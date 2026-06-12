"""
prompt_context.py

Engine-produced text blocks for prompt assembly.

V0.3.0+: applications own prompt *format* (template strings, ordering, rules).
The engine supplies factual strings — passive vision, memory, area text, etc. —
via ``build_prompt_context``. The default compound prompt in ``prompt.py`` is
one reference assembly; game projects can ignore it and compose their own.
"""

from dataclasses import dataclass

from src.agent import Agent
from src.perception import (
    build_passive_vision,
    get_available_interactions,
    get_available_look_targets,
)
from src.area import Area


@dataclass(frozen=True)
class PromptContext:
    """
    String variables the application layer can inject into its own templates.

    Example (future game project)::

        ctx = build_prompt_context(agent, area)
        prompt = MY_TEMPLATE.format(
            passive_vision=ctx.passive_vision,
            memory=ctx.memory,
            room=ctx.area_description,
            ...
        )
    """

    character: str
    passive_vision: str
    memory: str
    area_description: str
    grid_description: str
    compound_rules: str
    move_instructions: str
    look_and_interact: str
    output_format: str


def _character_block(agent: Agent) -> str:
    return (
        f"You are {agent.name}.\n"
        f"Your personality: {agent.personality}\n\n"
        f"Your detailed description: {agent.description}"
    )


def _compound_turn_rules() -> str:
    return """Each turn you may plan a **compound turn** executed in this order:
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
- You need to be adjacent or on the same tile as most objects to interact with them.
- turn_action "none": end after optional move/look without speaking or interacting.

Always respond with a single, valid JSON object. Do not add any text before or after the JSON."""


def _format_interact_block(agent: Agent, area: Area) -> str:
    interactions = get_available_interactions(agent, area)
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


def _look_and_interact_block(agent: Agent, area: Area) -> str:
    targets = get_available_look_targets(agent, area)
    lines = []
    if targets:
        lines.append("You can look at: " + ", ".join(targets))
    else:
        lines.append("You can look at: (nothing visible to examine)")
    interact_block = _format_interact_block(agent, area)
    if interact_block:
        lines.append("")
        lines.append(interact_block)
    lines.append("")
    lines.append(
        'Turn action: set turn_action to "speak" (with content), "interact" '
        '(with target + action_name when available), or "none".'
    )
    return "\n".join(lines)


def compound_output_format() -> str:
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


def build_prompt_context(agent: Agent, area: Area) -> PromptContext:
    """Collect engine-produced strings for one agent turn (no template assembly)."""
    memory_body = agent.memory.render_prompt_block(agent, area)
    return PromptContext(
        character=_character_block(agent),
        passive_vision=build_passive_vision(agent, area),
        memory=memory_body,
        area_description=area.get_area_description(),
        grid_description=area.format_grid_description(),
        compound_rules=_compound_turn_rules(),
        move_instructions=area.format_move_coordinate_rule(),
        look_and_interact=_look_and_interact_block(agent, area),
        output_format=compound_output_format(),
    )
