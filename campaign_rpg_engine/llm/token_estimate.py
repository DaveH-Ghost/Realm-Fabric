"""Rough prompt token estimates and input budget helpers (V0.4.2 / 1.5.2)."""

from __future__ import annotations

import os
from typing import Any

# Default demo session budget (V0.4.4). ~966 est. tokens pre-0.4.4; tightened after compaction.
DEFAULT_PROMPT_TOKEN_BUDGET = 650

# Hard input cap for LLM calls (1.5.2). Matches common Featherless 32k context.
DEFAULT_MAX_INPUT_TOKENS = 32768
DEFAULT_INPUT_WARNING_PERCENT = 90


def estimate_prompt_tokens(text: str) -> int:
    """
    Approximate input tokens for English prose (~4 characters per token).

    Not model-exact; good enough for hover hints before Run turn.
    """
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def get_max_input_tokens() -> int:
    """Return configured max input tokens (default 32768)."""
    raw = (os.environ.get("LLM_MAX_INPUT_TOKENS") or "").strip()
    if not raw:
        return DEFAULT_MAX_INPUT_TOKENS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_INPUT_TOKENS
    if value < 1:
        return DEFAULT_MAX_INPUT_TOKENS
    return value


def get_input_warning_percent() -> int:
    """Return warning percent of max input tokens (default 90, clamped 1–100)."""
    raw = (os.environ.get("LLM_INPUT_WARNING_PERCENT") or "").strip()
    if not raw:
        return DEFAULT_INPUT_WARNING_PERCENT
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_INPUT_WARNING_PERCENT
    return max(1, min(100, value))


def prompt_token_budget_status(prompt: str) -> dict[str, Any]:
    """Return estimate vs limit / warning threshold for *prompt*."""
    estimate = estimate_prompt_tokens(prompt)
    limit = get_max_input_tokens()
    warning_percent = get_input_warning_percent()
    warning_threshold = max(1, (limit * warning_percent) // 100)
    return {
        "estimate": estimate,
        "limit": limit,
        "warning_percent": warning_percent,
        "warning_threshold": warning_threshold,
        "over_warning": estimate >= warning_threshold,
        "over_limit": estimate > limit,
    }


def prompt_exceeds_max_input(prompt: str) -> tuple[bool, int, int]:
    """Return ``(over_limit, estimate, limit)`` for *prompt*."""
    status = prompt_token_budget_status(prompt)
    return bool(status["over_limit"]), int(status["estimate"]), int(status["limit"])
