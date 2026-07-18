"""
Prompt block model and renderer (V0.4.1b).

Sessions assemble LLM prompts from an ordered list of ``slot``, ``text``, and
``section`` blocks instead of a monolithic ``template.txt`` string.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from campaign_rpg_engine.llm.prompt_context import (
    PromptContext,
    _compound_turn_rules,
    compound_output_format,
    compound_output_format_relative,
    compound_turn_rules_relative,
    render_character_slot,
    render_grid_description_slot,
    render_look_and_interact_slot,
    render_move_instructions_slot,
    render_passive_vision_slot,
)
from campaign_rpg_engine.coordinate_mode import (
    COORDINATE_MODE_RELATIVE,
    normalize_coordinate_mode,
)


def _is_registered_plugin_slot(name: str) -> bool:
    from campaign_rpg_engine.prompt_slots.registry import is_prompt_slot_registered

    return is_prompt_slot_registered(name)

from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area
from campaign_rpg_engine.lorebook.matcher import build_scan_corpus, render_lorebook
from campaign_rpg_engine.lorebook.models import DEFAULT_LOREBOOK_CHAR_BUDGET, Lorebook
from campaign_rpg_engine.lorebook.scan_config import LorebookScanConfig
from campaign_rpg_engine.prompt_template import prompt_context_slots

BlockType = Literal["slot", "plugin_slot", "text", "section"]

EDITABLE_SECTION_NAMES = frozenset({"compound_rules", "output_format"})

SLOT_DESCRIPTIONS: dict[str, str] = {
    "character": "Agent name, personality, and detailed description",
    "passive_vision": "Passive vision, look hints, reachable and [far] object interactions",
    "memory": "Memory module render for the agent",
    "area_description": "Narrative description of the current area",
    "grid_description": "Grid bounds and coordinate instructions",
    "compound_rules": "Compound turn rules (editable as a section block)",
    "rules": "Alias for compound_rules",
    "move_instructions": "Move targets and move_speed guidance",
    "look_and_interact": "Deprecated — merged into passive_vision (0.6.0c); renders empty",
    "lorebook": "Inject matched entries from one loaded lorebook (requires lorebook_id option)",
    "output_format": "JSON output shape (editable as a section block)",
}

KNOWN_SLOT_NAMES = frozenset(SLOT_DESCRIPTIONS)


def list_registered_plugin_slot_names() -> list[str]:
    from campaign_rpg_engine.prompt_slots.registry import list_registered_prompt_slots

    return [
        name
        for name in list_registered_prompt_slots()
        if name not in KNOWN_SLOT_NAMES
    ]


SLOT_SETTINGS: dict[str, dict[str, Any]] = {
    "character": {
        "label": "Character",
        "fields": [
            {"key": "include_name", "label": "Name", "default": True},
            {"key": "include_personality", "label": "Personality", "default": True},
            {"key": "include_description", "label": "Description", "default": True},
        ],
        "min_enabled": 1,
    },
    "passive_vision": {
        "label": "Passive vision",
        "fields": [
            {"key": "include_you_are_at", "label": "You are at", "default": True},
            {
                "key": "include_entity_coordinates",
                "label": "Entity coordinates",
                "default": True,
            },
            {
                "key": "include_relative_bearing",
                "label": "Direction and distance",
                "default": False,
            },
        ],
        "min_enabled": 0,
    },
    "move_instructions": {
        "label": "Move instructions",
        "fields": [
            {
                "key": "include_coordinate_moves",
                "label": "Coordinate moves",
                "default": True,
            },
        ],
        "min_enabled": 0,
    },
}


@dataclass(frozen=True)
class PromptBlock:
    """One piece of a prompt layout."""

    type: BlockType
    name: str | None = None
    content: str | None = None
    options: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"type": self.type}
        if self.type in ("slot", "plugin_slot"):
            assert self.name is not None
            data["name"] = self.name
            if self.options:
                data["options"] = dict(self.options)
        elif self.type == "text":
            data["content"] = self.content or ""
        elif self.type == "section":
            assert self.name is not None
            data["name"] = self.name
            data["content"] = self.content or ""
        return data


def default_prompt_blocks() -> list[PromptBlock]:
    """Default layout matching ``profiles/default_compound/template.txt``."""
    return [
        PromptBlock(type="slot", name="character"),
        PromptBlock(type="text", content="\n\nPassive Vision:\n"),
        PromptBlock(type="slot", name="passive_vision"),
        PromptBlock(type="text", content="\n\n"),
        PromptBlock(type="slot", name="grid_description"),
        PromptBlock(type="text", content="\n\n"),
        PromptBlock(type="section", name="compound_rules", content=_compound_turn_rules()),
        PromptBlock(type="text", content="\n\n"),
        PromptBlock(type="slot", name="area_description"),
        PromptBlock(type="text", content="\n\n"),
        PromptBlock(type="slot", name="move_instructions"),
        PromptBlock(type="text", content="\n\nMemory:\n"),
        PromptBlock(type="slot", name="memory"),
        PromptBlock(type="text", content="\n\n"),
        PromptBlock(
            type="section",
            name="output_format",
            content=compound_output_format(),
        ),
    ]


def _validate_lorebook_slot(options: dict[str, Any] | None) -> str | None:
    if not options:
        return "lorebook slot requires options with lorebook_id."
    book_id = str(options.get("lorebook_id", "")).strip()
    if not book_id:
        return "lorebook slot requires options.lorebook_id."
    unknown = set(options) - {"lorebook_id"}
    if unknown:
        return (
            f"Unknown lorebook option(s): {', '.join(sorted(unknown))}. "
            "Allowed: lorebook_id."
        )
    return None


def _validate_slot_options(slot_name: str, options: dict[str, Any] | None) -> str | None:
    if not options:
        return None
    if slot_name not in SLOT_SETTINGS:
        return f"Slot {slot_name!r} does not support options."
    schema = SLOT_SETTINGS[slot_name]
    allowed = {field["key"] for field in schema["fields"]}
    unknown = set(options) - allowed
    if unknown:
        allowed_list = ", ".join(sorted(allowed))
        return f"Unknown option(s) for {slot_name!r}: {', '.join(sorted(unknown))}. Allowed: {allowed_list}."
    enabled = 0
    for field in schema["fields"]:
        key = field["key"]
        if key not in options:
            if field.get("default", False):
                enabled += 1
            continue
        if bool(options[key]):
            enabled += 1
    min_enabled = int(schema.get("min_enabled", 0))
    if enabled < min_enabled:
        return f"Slot {slot_name!r} requires at least {min_enabled} enabled option(s)."
    return None


def validate_prompt_blocks(blocks: list[PromptBlock]) -> str | None:
    """Return an error message if *blocks* is invalid."""
    if not blocks:
        return "At least one prompt block is required."
    for index, block in enumerate(blocks):
        prefix = f"Block {index + 1}"
        if block.type == "slot":
            if not block.name:
                return f"{prefix}: slot block requires name."
            if block.name not in KNOWN_SLOT_NAMES and not _is_registered_plugin_slot(
                block.name
            ):
                known = ", ".join(sorted(KNOWN_SLOT_NAMES))
                return f"{prefix}: unknown slot {block.name!r}. Known: {known}."
            if block.content is not None:
                return f"{prefix}: slot block must not include content."
            if block.name == "lorebook":
                opt_err = _validate_lorebook_slot(block.options)
            elif block.options:
                opt_err = _validate_slot_options(block.name, block.options)
            else:
                opt_err = None
            if opt_err:
                return f"{prefix}: {opt_err}"
        elif block.type == "plugin_slot":
            if not block.name:
                return f"{prefix}: plugin slot block requires name."
            if block.name in KNOWN_SLOT_NAMES:
                return (
                    f"{prefix}: {block.name!r} is an engine slot; use type 'slot' instead."
                )
            if not _is_registered_plugin_slot(block.name):
                known = ", ".join(list_registered_plugin_slot_names()) or "(none)"
                return f"{prefix}: unknown plugin slot {block.name!r}. Known: {known}."
            if block.content is not None:
                return f"{prefix}: plugin slot block must not include content."
            if block.options:
                return f"{prefix}: plugin slot blocks do not support options."
        elif block.type == "text":
            if block.content is None:
                return f"{prefix}: text block requires content."
            if block.name is not None:
                return f"{prefix}: text block must not include name."
        elif block.type == "section":
            if not block.name:
                return f"{prefix}: section block requires name."
            if block.name not in EDITABLE_SECTION_NAMES:
                allowed = ", ".join(sorted(EDITABLE_SECTION_NAMES))
                return f"{prefix}: section {block.name!r} is not editable. Allowed: {allowed}."
            if block.content is None:
                return f"{prefix}: section block requires content."
        else:
            return f"{prefix}: unknown type {block.type!r}."
    return None


def prompt_blocks_from_dicts(items: list[dict[str, Any]]) -> tuple[list[PromptBlock], str | None]:
    """Parse API/JSON payloads into ``PromptBlock`` instances."""
    blocks: list[PromptBlock] = []
    for index, raw in enumerate(items):
        prefix = f"Block {index + 1}"
        if not isinstance(raw, dict):
            return [], f"{prefix}: expected an object."
        block_type = raw.get("type")
        if block_type not in ("slot", "plugin_slot", "text", "section"):
            return [], f"{prefix}: type must be slot, plugin_slot, text, or section."
        name = raw.get("name")
        content = raw.get("content")
        if name is not None:
            name = str(name).strip()
            if not name:
                name = None
        if content is not None:
            content = str(content)
        options_raw = raw.get("options")
        options: dict[str, Any] | None = None
        if options_raw is not None:
            if not isinstance(options_raw, dict):
                return [], f"{prefix}: options must be an object."
            options = {str(key): value for key, value in options_raw.items()}
        blocks.append(
            PromptBlock(type=block_type, name=name, content=content, options=options)
        )
    err = validate_prompt_blocks(blocks)
    if err:
        return [], err
    return blocks, None


def render_section_block(block: PromptBlock, coordinate_mode: str = "full") -> str:
    """Render a section block, applying relative-mode overrides for known sections."""
    if normalize_coordinate_mode(coordinate_mode) == COORDINATE_MODE_RELATIVE:
        if block.name == "compound_rules" or block.name == "rules":
            return compound_turn_rules_relative()
        if block.name == "output_format":
            return compound_output_format_relative()
    return block.content or ""


def render_slot_block(
    block: PromptBlock,
    ctx: PromptContext,
    *,
    agent: Agent | None = None,
    area: Area | None = None,
    session: object | None = None,
    vision_units: str = "",
    units_per_tile: int | None = None,
    coordinate_mode: str = "full",
    lorebooks: dict[str, Lorebook] | None = None,
    lorebook_char_budget: int = DEFAULT_LOREBOOK_CHAR_BUDGET,
    lorebook_scan_config: LorebookScanConfig | None = None,
    passive_vision: str = "",
) -> str:
    """Render one slot block, applying per-block options when supported."""
    assert block.name is not None
    if block.name == "lorebook":
        if agent is None or area is None or not block.options:
            return ""
        book_id = str(block.options.get("lorebook_id", "")).strip()
        books = lorebooks or {}
        book = books.get(book_id)
        if book is None:
            return ""
        corpus = build_scan_corpus(
            agent=agent,
            area=area,
            memory_text=ctx.memory,
            passive_vision=passive_vision,
            scan_config=lorebook_scan_config,
        )
        return render_lorebook(book, corpus, char_budget=lorebook_char_budget)
    if block.name == "character":
        return render_character_slot(ctx, block.options)
    if block.name == "passive_vision":
        return render_passive_vision_slot(
            ctx,
            block.options,
            agent=agent,
            area=area,
            vision_units=vision_units,
            units_per_tile=units_per_tile,
            coordinate_mode=coordinate_mode,
        )
    if block.name == "move_instructions":
        return render_move_instructions_slot(
            ctx,
            block.options,
            agent=agent,
            area=area,
            vision_units=vision_units,
            units_per_tile=units_per_tile,
            coordinate_mode=coordinate_mode,
        )
    if block.name == "grid_description":
        return render_grid_description_slot(
            ctx,
            area=area,
            coordinate_mode=coordinate_mode,
            vision_units=vision_units,
            units_per_tile=units_per_tile,
        )
    if block.name == "look_and_interact":
        return render_look_and_interact_slot(
            ctx,
            agent=agent,
            area=area,
            vision_units=vision_units,
            units_per_tile=units_per_tile,
        )
    if _is_registered_plugin_slot(block.name):
        if session is None or agent is None or area is None:
            return ""
        from campaign_rpg_engine.prompt_slots.registry import render_registered_prompt_slot
        from campaign_rpg_engine.session import Session

        if not isinstance(session, Session):
            return ""
        return render_registered_prompt_slot(
            block.name,
            session=session,
            agent=agent,
            area=area,
            ctx=ctx,
            options=block.options,
        )
    return prompt_context_slots(ctx).get(block.name, "")


def render_prompt_blocks(
    blocks: list[PromptBlock],
    ctx: PromptContext,
    *,
    agent: Agent | None = None,
    area: Area | None = None,
    session: object | None = None,
    vision_units: str = "",
    units_per_tile: int | None = None,
    coordinate_mode: str = "full",
    lorebooks: dict[str, Lorebook] | None = None,
    lorebook_char_budget: int = DEFAULT_LOREBOOK_CHAR_BUDGET,
    lorebook_scan_config: LorebookScanConfig | None = None,
    passive_vision: str = "",
) -> str:
    """Render *blocks* using live values from *ctx*."""
    vision_text = passive_vision or ctx.passive_vision
    parts: list[str] = []
    for block in blocks:
        if block.type == "text":
            parts.append(block.content or "")
        elif block.type in ("slot", "plugin_slot"):
            parts.append(
                render_slot_block(
                    block,
                    ctx,
                    agent=agent,
                    area=area,
                    session=session,
                    vision_units=vision_units,
                    units_per_tile=units_per_tile,
                    coordinate_mode=coordinate_mode,
                    lorebooks=lorebooks,
                    lorebook_char_budget=lorebook_char_budget,
                    lorebook_scan_config=lorebook_scan_config,
                    passive_vision=vision_text,
                )
            )
        elif block.type == "section":
            assert block.name is not None
            parts.append(render_section_block(block, coordinate_mode))
    return "".join(parts).strip()


def enrich_blocks_with_previews(
    blocks: list[PromptBlock],
    ctx: PromptContext,
    *,
    agent: Agent | None = None,
    area: Area | None = None,
    session: object | None = None,
    vision_units: str = "",
    units_per_tile: int | None = None,
    coordinate_mode: str = "full",
    lorebooks: dict[str, Lorebook] | None = None,
    lorebook_char_budget: int = DEFAULT_LOREBOOK_CHAR_BUDGET,
    lorebook_scan_config: LorebookScanConfig | None = None,
    passive_vision: str = "",
) -> list[dict[str, Any]]:
    """Serialize blocks and attach rendered previews for slot rows."""
    vision_text = passive_vision or ctx.passive_vision
    enriched: list[dict[str, Any]] = []
    for block in blocks:
        data = block.to_dict()
        if block.type in ("slot", "plugin_slot"):
            data["preview"] = render_slot_block(
                block,
                ctx,
                agent=agent,
                area=area,
                session=session,
                vision_units=vision_units,
                units_per_tile=units_per_tile,
                coordinate_mode=coordinate_mode,
                lorebooks=lorebooks,
                lorebook_char_budget=lorebook_char_budget,
                lorebook_scan_config=lorebook_scan_config,
                passive_vision=vision_text,
            )
        elif block.type == "section":
            data["preview"] = render_section_block(block, coordinate_mode)
        enriched.append(data)
    return enriched


def prompt_slot_catalog(ctx: PromptContext) -> list[dict[str, Any]]:
    """JSON-friendly slot list with descriptions and full rendered previews."""
    slots = prompt_context_slots(ctx)
    items: list[dict[str, Any]] = []
    for name in sorted(slots):
        if name == "rules":
            continue
        items.append(
            {
                "name": name,
                "description": SLOT_DESCRIPTIONS.get(name, ""),
                "preview": slots[name],
            }
        )
    return items


def _default_section_content() -> dict[str, str]:
    content: dict[str, str] = {}
    for block in default_prompt_blocks():
        if block.type == "section" and block.name is not None:
            content[block.name] = block.content or ""
    return content


def prompt_block_catalog() -> dict[str, Any]:
    """Describe addable block types for campaign-rpg-studio (extensible for new schemas)."""
    section_defaults = _default_section_content()
    slot_options = [
        {
            "name": name,
            "description": SLOT_DESCRIPTIONS.get(name, ""),
        }
        for name in sorted(KNOWN_SLOT_NAMES)
        if name != "rules"
    ]
    section_options = [
        {
            "name": name,
            "description": SLOT_DESCRIPTIONS.get(name, ""),
            "default_content": section_defaults.get(name, ""),
        }
        for name in sorted(EDITABLE_SECTION_NAMES)
    ]
    from campaign_rpg_engine.prompt_slots.registry import (
        get_prompt_slot_registration,
        list_registered_prompt_slots,
    )

    plugin_slot_options = []
    for name in list_registered_prompt_slots():
        if name in KNOWN_SLOT_NAMES:
            continue
        reg = get_prompt_slot_registration(name)
        plugin_slot_options.append(
            {
                "name": name,
                "description": reg.description if reg else "",
            }
        )
    return {
        "block_types": [
            {
                "type": "slot",
                "label": "Dynamic slot",
                "description": "Engine-computed content inserted at render time.",
                "options": slot_options,
            },
            {
                "type": "plugin_slot",
                "label": "Plugin slot",
                "description": "Content from an enabled plugin prompt slot.",
                "options": plugin_slot_options,
            },
            {
                "type": "text",
                "label": "Static text",
                "description": "Fixed prose or labels copied verbatim into the prompt.",
                "default_content": "",
            },
            {
                "type": "section",
                "label": "Editable section",
                "description": "Named static section; starts from profile default content.",
                "options": section_options,
            },
        ],
        "slot_settings": SLOT_SETTINGS,
        "lorebook_slot": {
            "name": "lorebook",
            "description": SLOT_DESCRIPTIONS["lorebook"],
            "requires_option": "lorebook_id",
        },
    }
