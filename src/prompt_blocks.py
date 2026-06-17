"""
Prompt block model and renderer (V0.4.1b).

Sessions assemble LLM prompts from an ordered list of ``slot``, ``text``, and
``section`` blocks instead of a monolithic ``template.txt`` string.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from src.llm.prompt_context import (
    PromptContext,
    _compound_turn_rules,
    compound_output_format,
)
from src.prompt_template import prompt_context_slots

BlockType = Literal["slot", "text", "section"]

EDITABLE_SECTION_NAMES = frozenset({"compound_rules", "output_format"})

SLOT_DESCRIPTIONS: dict[str, str] = {
    "character": "Agent name, personality, and detailed description",
    "passive_vision": "Current passive vision for the agent",
    "memory": "Memory module render for the agent",
    "area_description": "Narrative description of the current area",
    "grid_description": "Grid bounds and coordinate instructions",
    "compound_rules": "Compound turn rules (editable as a section block)",
    "rules": "Alias for compound_rules",
    "move_instructions": "Move targets and move_speed guidance",
    "look_and_interact": "Look targets and available object interactions",
    "output_format": "JSON output shape (editable as a section block)",
}

KNOWN_SLOT_NAMES = frozenset(SLOT_DESCRIPTIONS)


@dataclass(frozen=True)
class PromptBlock:
    """One piece of a prompt layout."""

    type: BlockType
    name: str | None = None
    content: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"type": self.type}
        if self.type == "slot":
            assert self.name is not None
            data["name"] = self.name
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
        PromptBlock(type="text", content="\n\n"),
        PromptBlock(type="slot", name="look_and_interact"),
        PromptBlock(type="text", content="\n\nMemory:\n"),
        PromptBlock(type="slot", name="memory"),
        PromptBlock(
            type="text",
            content=(
                "\n\nPlan your full compound turn (move, then look, then turn action)."
                "\n\nSpoken text should be things you say out loud (~500 characters; "
                "excess is trimmed at sentence boundaries).\n\n"
            ),
        ),
        PromptBlock(
            type="section",
            name="output_format",
            content=compound_output_format(),
        ),
    ]


def validate_prompt_blocks(blocks: list[PromptBlock]) -> str | None:
    """Return an error message if *blocks* is invalid."""
    if not blocks:
        return "At least one prompt block is required."
    for index, block in enumerate(blocks):
        prefix = f"Block {index + 1}"
        if block.type == "slot":
            if not block.name:
                return f"{prefix}: slot block requires name."
            if block.name not in KNOWN_SLOT_NAMES:
                known = ", ".join(sorted(KNOWN_SLOT_NAMES))
                return f"{prefix}: unknown slot {block.name!r}. Known: {known}."
            if block.content is not None:
                return f"{prefix}: slot block must not include content."
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
        if block_type not in ("slot", "text", "section"):
            return [], f"{prefix}: type must be slot, text, or section."
        name = raw.get("name")
        content = raw.get("content")
        if name is not None:
            name = str(name).strip()
            if not name:
                name = None
        if content is not None:
            content = str(content)
        blocks.append(PromptBlock(type=block_type, name=name, content=content))
    err = validate_prompt_blocks(blocks)
    if err:
        return [], err
    return blocks, None


def render_prompt_blocks(blocks: list[PromptBlock], ctx: PromptContext) -> str:
    """Render *blocks* using live values from *ctx*."""
    slots = prompt_context_slots(ctx)
    parts: list[str] = []
    for block in blocks:
        if block.type == "text":
            parts.append(block.content or "")
        elif block.type == "slot":
            assert block.name is not None
            parts.append(slots.get(block.name, ""))
        elif block.type == "section":
            assert block.name is not None
            parts.append(block.content or "")
    return "".join(parts).strip()


def prompt_slot_catalog(
    ctx: PromptContext,
    *,
    preview_limit: int = 200,
) -> list[dict[str, Any]]:
    """JSON-friendly slot list with descriptions and previews."""
    slots = prompt_context_slots(ctx)
    items: list[dict[str, Any]] = []
    for name in sorted(slots):
        if name == "rules":
            continue
        preview = slots[name]
        if len(preview) > preview_limit:
            preview = preview[: preview_limit - 1] + "…"
        items.append(
            {
                "name": name,
                "description": SLOT_DESCRIPTIONS.get(name, ""),
                "preview": preview,
            }
        )
    return items
