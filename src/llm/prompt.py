"""
prompt.py

Default compound-turn prompt assembly for V0.2.5+.

Game/application projects should prefer ``build_prompt_context`` and compose
their own templates; this module keeps the built-in reference prompt.
"""

from src.agent import Agent
from src.llm.prompt_context import PromptContext, build_prompt_context
from src.area import Area


FEW_SHOT_COMPOUND_EXAMPLES = """
Example 1: Move, look, and speak

Context:
Passive Vision:
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
Passive Vision:
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
Passive Vision:
You are at (1, 1).
You may move to any coordinate (x, y) where x is an integer from 0 to 4 and y is an integer from 0 to 4.

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


def assemble_default_compound_prompt(
    ctx: PromptContext, *, include_examples: bool = False
) -> str:
    """Assemble the reference compound prompt from a ``PromptContext``."""
    parts = [
        ctx.character,
        "",
        "Passive Vision:",
        ctx.passive_vision,
        "",
        ctx.grid_description,
        "",
        ctx.compound_rules,
        "",
        ctx.area_description,
        "",
        ctx.move_instructions,
        "",
        ctx.look_and_interact,
        "",
        "Memory:",
        ctx.memory,
        "",
        "Plan your full compound turn (move, then look, then turn action).",
        "",
        "You may speak up to five sentences. Spoken text should be things you say out loud.",
        "",
        ctx.output_format,
    ]
    if include_examples:
        parts.extend(["", "Here are compound turn examples:", FEW_SHOT_COMPOUND_EXAMPLES])
    return "\n".join(parts).strip()


def build_compound_prompt(
    agent: Agent, area: Area, include_examples: bool = False
) -> str:
    """Build the default compound LLM prompt for one agent turn."""
    ctx = build_prompt_context(agent, area)
    return assemble_default_compound_prompt(ctx, include_examples=include_examples)


def build_prompt(agent: Agent, area: Area, include_examples: bool = False) -> str:
    """Alias for the compound turn prompt."""
    return build_compound_prompt(agent, area, include_examples=include_examples)
