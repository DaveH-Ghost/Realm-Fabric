"""Memory module text formatting (common render, salient policy, summary batches)."""
from __future__ import annotations

from campaign_rpg_engine.memory_modules.formatting.common import (
    REASONING_WINDOW,
    format_own_turn,
    format_stored_turns_block,
    format_witnessed_events,
    join_lines,
    join_step_results,
    should_include_reasoning,
)
from campaign_rpg_engine.memory_modules.formatting.salient import (
    STEP_SALIENCE,
    WITNESS_SALIENCE,
    select_salient_steps,
    step_salience,
)
from campaign_rpg_engine.memory_modules.formatting.summary import format_turns_batch_for_summary

__all__ = [
    "REASONING_WINDOW",
    "STEP_SALIENCE",
    "WITNESS_SALIENCE",
    "format_own_turn",
    "format_stored_turns_block",
    "format_turns_batch_for_summary",
    "format_witnessed_events",
    "join_lines",
    "join_step_results",
    "select_salient_steps",
    "should_include_reasoning",
    "step_salience",
]
