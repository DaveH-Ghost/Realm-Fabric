"""
prompt.py

Default compound-turn prompt assembly for V0.2.5+.

Game/application projects should prefer ``build_prompt_context`` and compose
their own templates; this module keeps the built-in reference prompt.
"""
from __future__ import annotations

from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.game_profile import default_compound_profile
from campaign_rpg_engine.llm.prompt_context import PromptContext, build_prompt_context
from campaign_rpg_engine.area import Area


def assemble_default_compound_prompt(
    ctx: PromptContext, *, include_examples: bool = False
) -> str:
    """Assemble the reference compound prompt from a ``PromptContext``."""
    return default_compound_profile().build_prompt(
        ctx, include_examples=include_examples
    )


def build_compound_prompt(
    agent: Agent, area: Area, include_examples: bool = False
) -> str:
    """Build the default compound LLM prompt for one agent turn."""
    ctx = build_prompt_context(agent, area)
    return assemble_default_compound_prompt(ctx, include_examples=include_examples)


def build_prompt(agent: Agent, area: Area, include_examples: bool = False) -> str:
    """Alias for the compound turn prompt."""
    return build_compound_prompt(agent, area, include_examples=include_examples)


# Re-export for tests and callers that reference few-shots directly.
def few_shot_compound_examples() -> str:
    return default_compound_profile().few_shot_examples


FEW_SHOT_COMPOUND_EXAMPLES = few_shot_compound_examples()
