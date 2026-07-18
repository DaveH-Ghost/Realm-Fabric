"""
prompt_context.py

Engine-produced text blocks for prompt assembly.

V0.3.0+: applications own prompt *format* (template strings, ordering, rules).
The engine supplies factual strings — passive vision, memory, area text, etc. —
via ``build_prompt_context``. The default compound prompt in ``prompt.py`` is
one reference assembly; game projects can ignore it and compose their own.
"""
from __future__ import annotations

from dataclasses import dataclass

from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area
from campaign_rpg_engine.move_target import (
    format_move_instructions,
    normalize_move_instructions_options,
)
from campaign_rpg_engine.perception import (
    build_passive_vision,
    normalize_passive_vision_options,
)


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
    character_name: str
    character_personality: str
    character_description: str
    passive_vision: str
    memory: str
    area_description: str
    grid_description: str
    compound_rules: str
    move_instructions: str
    look_and_interact: str
    output_format: str


DEFAULT_CHARACTER_OPTIONS: dict[str, bool] = {
    "include_name": True,
    "include_personality": True,
    "include_description": True,
}


def normalize_character_options(
    options: dict[str, object] | None,
) -> dict[str, bool]:
    """Merge *options* with defaults for character slot rendering."""
    merged = dict(DEFAULT_CHARACTER_OPTIONS)
    if options:
        for key in DEFAULT_CHARACTER_OPTIONS:
            if key in options:
                merged[key] = bool(options[key])
    return merged


def _join_character_parts(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    result = parts[0]
    for segment in parts[1:]:
        if segment.startswith("Your detailed description:"):
            result += "\n\n" + segment
        else:
            result += "\n" + segment
    return result


def character_block(
    agent: Agent,
    *,
    include_name: bool = True,
    include_personality: bool = True,
    include_description: bool = True,
) -> str:
    """Render the character slot with optional field toggles."""
    opts = normalize_character_options(
        {
            "include_name": include_name,
            "include_personality": include_personality,
            "include_description": include_description,
        }
    )
    parts: list[str] = []
    if opts["include_name"]:
        parts.append(f"You are {agent.name}.")
    if opts["include_personality"]:
        parts.append(f"Personality: {agent.personality}")
    if opts["include_description"]:
        parts.append(f"Description: {agent.description}")
    return _join_character_parts(parts)


def render_character_slot(
    ctx: PromptContext,
    options: dict[str, object] | None = None,
) -> str:
    """Render character slot lines from context parts and block options."""
    opts = normalize_character_options(options)
    parts: list[str] = []
    if opts["include_name"]:
        parts.append(ctx.character_name)
    if opts["include_personality"]:
        parts.append(ctx.character_personality)
    if opts["include_description"]:
        parts.append(ctx.character_description)
    return _join_character_parts(parts)


def render_passive_vision_slot(
    ctx: PromptContext,
    options: dict[str, object] | None = None,
    *,
    agent: Agent | None = None,
    area: Area | None = None,
    vision_units: str = "",
    units_per_tile: int | None = None,
    coordinate_mode: str = "full",
) -> str:
    """Render passive vision with optional you-are-at / coordinate toggles."""
    from campaign_rpg_engine.coordinate_mode import apply_passive_vision_mode

    opts = apply_passive_vision_mode(
        options,
        coordinate_mode,
        normalize=normalize_passive_vision_options,
    )
    if agent is not None and area is not None:
        return build_passive_vision(
            agent,
            area,
            include_you_are_at=opts["include_you_are_at"],
            include_entity_coordinates=opts["include_entity_coordinates"],
            include_relative_bearing=opts["include_relative_bearing"],
            vision_units=vision_units,
            units_per_tile=units_per_tile,
        )
    return ctx.passive_vision


def render_move_instructions_slot(
    ctx: PromptContext,
    options: dict[str, object] | None = None,
    *,
    agent: Agent | None = None,
    area: Area | None = None,
    vision_units: str = "",
    units_per_tile: int | None = None,
    coordinate_mode: str = "full",
) -> str:
    """Render move instructions with optional coordinate-move toggle."""
    from campaign_rpg_engine.coordinate_mode import apply_move_instructions_mode

    opts = apply_move_instructions_mode(
        options,
        coordinate_mode,
        normalize=normalize_move_instructions_options,
    )
    if agent is not None and area is not None:
        return format_move_instructions(
            agent,
            area,
            include_coordinate_moves=opts["include_coordinate_moves"],
            vision_units=vision_units,
            units_per_tile=units_per_tile,
        )
    return ctx.move_instructions


def _character_block(agent: Agent) -> str:
    return character_block(agent)


def _turn_verbs_rules_line() -> str:
    from campaign_rpg_engine.turn_verbs.registry import list_registered_turn_verbs

    verbs = list_registered_turn_verbs()
    if not verbs:
        return (
            "- verb: action \"verb\" + verb (special/inventory id) + optional target."
        )
    listed = ", ".join(verbs)
    return (
        f"- verb: action \"verb\" + verb (special/inventory id; "
        f"one of: {listed}) + optional target."
    )


def _compound_turn_rules() -> str:
    verb_line = _turn_verbs_rules_line()
    return f"""Compound turn order: move → look → speak → action.

Rules:
- Plan from current position and vision; move runs first, then look, speak, and action.
- move: "x,y", entity id (obj_* / agent_*), or null to stay; stay in grid bounds.
- look: entity id with [?] in passive vision for hidden detail, or null.
- Hidden detail: [?]; stale examined: [?] [changed].
- Object actions marked [far] are out of reach this turn — prefer move toward that object so you can speak/emote while approaching; interact still walks closer but may not finish.
- say: spoken dialogue or null.
- interact: action "interact" + target + verb. verb must be an exact action name listed under that object in passive vision (including [far] ones); do not invent verbs. For roleplay that is not a listed action, use emote instead.
- emote: nonverbal beat; verb=past-tense phrase (nodded; sat down); optional target. Results are tagged [emote].
- [emote]: roleplay gesture/expression — it does not move entities or change objects, but witnesses remember it and it can matter socially.
{verb_line}
- action "none": skip interact/emote/special after optional move/look/speak.

Reply with a single valid JSON object only."""


def compound_turn_rules_relative() -> str:
    verb_line = _turn_verbs_rules_line()
    return f"""Compound turn order: move → look → speak → action.

Rules:
- Plan from current position and vision; move runs first, then look, speak, and action.
- move: entity id (obj_* / agent_*), or null to stay.
- look: entity id with [?] in passive vision for hidden detail, or null.
- Hidden detail: [?]; stale examined: [?] [changed].
- Object actions marked [far] are out of reach this turn — prefer move toward that object so you can speak/emote while approaching; interact still walks closer but may not finish.
- say: spoken dialogue or null.
- interact: action "interact" + target + verb. verb must be an exact action name listed under that object in passive vision (including [far] ones); do not invent verbs. For roleplay that is not a listed action, use emote instead.
- emote: nonverbal beat; verb=past-tense phrase (nodded; sat down); optional target. Results are tagged [emote].
- [emote]: roleplay gesture/expression — it does not move entities or change objects, but witnesses remember it and it can matter socially.
{verb_line}
- action "none": skip interact/emote/special after optional move/look/speak.

Reply with a single valid JSON object only."""


def look_and_interact_block(
    agent: Agent,
    area: Area,
    *,
    vision_units: str = "",
    units_per_tile: int | None = None,
) -> str:
    """Deprecated (0.6.0c): look targets and interactions live in passive vision."""
    del agent, area, vision_units, units_per_tile
    return ""


def render_look_and_interact_slot(
    ctx: PromptContext,
    *,
    agent: Agent | None = None,
    area: Area | None = None,
    vision_units: str = "",
    units_per_tile: int | None = None,
) -> str:
    """Deprecated slot alias — content merged into passive_vision (0.6.0c)."""
    del ctx, agent, area, vision_units, units_per_tile
    return ""


def _look_and_interact_block(agent: Agent, area: Area) -> str:
    return look_and_interact_block(agent, area)


def compound_output_format() -> str:
    return (
        "JSON only (no markdown):\n"
        "{\n"
        '  "reasoning": "private thoughts (~400 chars max)",\n'
        '  "move": "2,3" | "obj_ball_01" | null,\n'
        '  "look": "obj_ball_01" | null,\n'
        '  "say": "spoken dialogue (~500 chars max) or null",\n'
        '  "action": "interact" | "emote" | "verb" | "none",\n'
        '  "target": "obj_* | agent_* | short aimed-at text | null",\n'
        '  "verb": "object action | emote phrase | special/inventory id | null"\n'
        "}"
    )


def compound_output_format_relative() -> str:
    return (
        "JSON only (no markdown):\n"
        "{\n"
        '  "reasoning": "private thoughts (~400 chars max)",\n'
        '  "move": "obj_ball_01" | null,\n'
        '  "look": "obj_ball_01" | null,\n'
        '  "say": "spoken dialogue (~500 chars max) or null",\n'
        '  "action": "interact" | "emote" | "verb" | "none",\n'
        '  "target": "obj_* | agent_* | short aimed-at text | null",\n'
        '  "verb": "object action | emote phrase | special/inventory id | null"\n'
        "}"
    )


def render_grid_description_slot(
    ctx: PromptContext,
    *,
    area: Area | None = None,
    coordinate_mode: str = "full",
    vision_units: str = "",
    units_per_tile: int | None = None,
) -> str:
    if area is not None:
        return area.format_grid_description(
            coordinate_mode=coordinate_mode,
            vision_units=vision_units,
            units_per_tile=units_per_tile,
        )
    return ctx.grid_description


def build_prompt_context(agent: Agent, area: Area) -> PromptContext:
    """Collect engine-produced strings for one agent turn (no template assembly)."""
    memory_body = agent.memory.render_prompt_block(agent, area)
    return PromptContext(
        character=_character_block(agent),
        character_name=f"You are {agent.name}.",
        character_personality=f"Personality: {agent.personality}",
        character_description=f"Description: {agent.description}",
        passive_vision=build_passive_vision(agent, area),
        memory=memory_body,
        area_description=area.get_area_description(),
        grid_description=area.format_grid_description(),
        compound_rules=_compound_turn_rules(),
        move_instructions=format_move_instructions(agent, area),
        look_and_interact=_look_and_interact_block(agent, area),
        output_format=compound_output_format(),
    )
