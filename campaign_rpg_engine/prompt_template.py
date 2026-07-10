"""
prompt_template.py

V0.3.0c — application-layer prompt layout via {{slot}} substitution.

The engine builds factual strings in ``PromptContext``; templates only
control ordering and prose wrappers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from campaign_rpg_engine.llm.prompt_context import PromptContext

_SLOT_PATTERN = re.compile(r"\{\{(\w+)\}\}")


def prompt_context_slots(ctx: PromptContext) -> dict[str, str]:
    """Map a ``PromptContext`` to template slot names."""
    return {
        "character": ctx.character,
        "passive_vision": ctx.passive_vision,
        "memory": ctx.memory,
        "area_description": ctx.area_description,
        "grid_description": ctx.grid_description,
        "compound_rules": ctx.compound_rules,
        "rules": ctx.compound_rules,
        "move_instructions": ctx.move_instructions,
        "look_and_interact": ctx.look_and_interact,
        "output_format": ctx.output_format,
    }


@dataclass(frozen=True)
class PromptTemplate:
    """String template with ``{{slot}}`` placeholders filled from context."""

    text: str

    @classmethod
    def from_file(cls, path: Path | str) -> PromptTemplate:
        return cls(Path(path).read_text(encoding="utf-8"))

    def render(self, slots: dict[str, str]) -> str:
        """Substitute ``{{name}}`` tokens; unknown slots are left unchanged."""

        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            return slots.get(key, match.group(0))

        return _SLOT_PATTERN.sub(replace, self.text).strip()

    def render_context(self, ctx: PromptContext) -> str:
        return self.render(prompt_context_slots(ctx))
