"""Rough prompt token estimates for UI hints (V0.4.2)."""

# Default demo session budget (V0.4.4). ~966 est. tokens pre-0.4.4; tightened after compaction.
DEFAULT_PROMPT_TOKEN_BUDGET = 650


def estimate_prompt_tokens(text: str) -> int:
    """
    Approximate input tokens for English prose (~4 characters per token).

    Not model-exact; good enough for hover hints before Run turn.
    """
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)
