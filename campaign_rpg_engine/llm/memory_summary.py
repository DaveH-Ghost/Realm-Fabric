"""LLM rolling memory summary generation (V0.2.5e)."""
from __future__ import annotations

from campaign_rpg_engine.llm.client import get_text_completion
from campaign_rpg_engine.log_utils import log_error, log_turn


def log_consolidation_error(message: str, exc: Exception) -> None:
    """Log a rolling-summary consolidation failure (I/O layer)."""
    log_error(message, exc)


def build_rolling_summary_prompt(
    *,
    agent_name: str,
    previous_summary: str,
    batch_text: str,
    max_chars: int,
) -> str:
    prior = (
        previous_summary.strip()
        if previous_summary.strip()
        else "(No prior summary — this is the first consolidation.)"
    )
    return f"""You maintain a rolling memory summary for {agent_name} in a grid-area simulation.

Update the agent's memory summary by merging:
1. The previous summary (if any)
2. The new turn batch below

Keep facts the agent would need later: locations, object changes, who said what, important actions, relationships, and open threads. Drop redundant move/look noise unless it mattered.

Rules:
- Write in second person ("You…") or neutral past tense about {agent_name}.
- Be concise but preserve salient details.
- The summary must be at most {max_chars} characters, any information beyond that will be truncated.
- Put the most important facts first — if the summary is too long it may be truncated at the end, so lead with what the agent must not forget.
- Do not invent events not present in the inputs.
- Respond with ONLY the updated summary text — no JSON, labels, or markdown.

Previous summary:
{prior}

New turns to merge:
{batch_text}
""".strip()


def generate_rolling_summary(
    *,
    agent_name: str,
    previous_summary: str,
    batch_text: str,
    max_chars: int,
    turn_number: int | None = None,
) -> str:
    """Call the LLM to produce an updated rolling summary (plain-text response)."""
    prompt = build_rolling_summary_prompt(
        agent_name=agent_name,
        previous_summary=previous_summary,
        batch_text=batch_text,
        max_chars=max_chars,
    )
    response = get_text_completion(prompt, temperature=0.3)
    summary = str(response.parsed).strip()
    if not summary:
        raise RuntimeError("LLM returned empty summary")
    if len(summary) > max_chars:
        summary = summary[: max_chars - 1] + "…"

    tokens = None
    if response.total_tokens is not None:
        tokens = {
            "prompt": response.prompt_tokens,
            "completion": response.completion_tokens,
            "total": response.total_tokens,
        }

    log_turn(
        turn_number or 0,
        phase="memory_summary",
        prompt=prompt,
        raw_output=response.raw_response,
        result=summary,
        tokens=tokens,
    )

    return summary
