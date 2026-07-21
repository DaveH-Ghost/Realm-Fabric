"""LLM rolling memory summary generation (V0.2.5e)."""

from __future__ import annotations

from collections.abc import Sequence

from campaign_rpg_engine.llm.client import get_text_completion
from campaign_rpg_engine.log_utils import exception_already_logged, log_error, log_turn


def log_consolidation_error(
    message: str,
    exc: Exception,
    *,
    turn_number: int = 0,
    phase: str | None = None,
    prompt: str | None = None,
    raw_output: str | None = None,
) -> None:
    """Log a rolling-summary / affinity consolidation failure (I/O layer)."""
    if exception_already_logged(exc):
        return
    log_error(
        message,
        exc,
        turn_number=turn_number,
        phase=phase,
        prompt=prompt,
        raw_output=raw_output,
    )


def format_consolidation_identity_preamble(
    *,
    personality: str = "",
    appearance: str = "",
    other_agents: Sequence[tuple[str, str]] = (),
) -> str:
    """
    Shared identity block for rolling-summary and affinity consolidation prompts.

    ``appearance`` is the agent's passive (non-detailed) description.
    ``other_agents`` is ``(name, passive_description)`` for co-present agents.
    """
    pers = personality.strip() or "(none)"
    app = appearance.strip() or "(none)"
    if other_agents:
        others = "\n".join(
            f"{name}, {(desc or '').strip() or '(no description)'}"
            for name, desc in other_agents
        )
    else:
        others = "(none)"
    return (
        f"Your personality:\n{pers}\n"
        f"Your appearance:\n{app}\n"
        f"Other Agents in this area:\n{others}"
    )


def other_agents_from_snapshot_extra(extra: dict | None) -> tuple[tuple[str, str], ...]:
    """Normalize ``extra['other_agents']`` from a consolidation snapshot."""
    rows = (extra or {}).get("other_agents") or []
    out: list[tuple[str, str]] = []
    for row in rows:
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            out.append((str(row[0]), str(row[1])))
    return tuple(out)


def build_rolling_summary_prompt(
    *,
    agent_name: str,
    previous_summary: str,
    batch_text: str,
    max_chars: int,
    personality: str = "",
    appearance: str = "",
    other_agents: Sequence[tuple[str, str]] = (),
) -> str:
    prior = (
        previous_summary.strip()
        if previous_summary.strip()
        else "(No prior summary — this is the first consolidation.)"
    )
    identity = format_consolidation_identity_preamble(
        personality=personality,
        appearance=appearance,
        other_agents=other_agents,
    )
    return f"""You maintain a rolling memory summary for {agent_name} in a grid-area simulation.

{identity}

Update the agent's memory summary by merging:
1. The previous summary (if any)
2. The new turn batch below

Keep facts the agent would need later: locations, object changes, who said what, important actions, relationships, and open threads. Drop redundant move/look noise unless it mattered.

Rules:
- Write in second person ("You…") or neutral past tense about {agent_name}.
- Match pronouns and gendered language to the personality and appearance above.
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
    personality: str = "",
    appearance: str = "",
    other_agents: Sequence[tuple[str, str]] = (),
) -> str:
    """Call the LLM to produce an updated rolling summary (plain-text response)."""
    prompt = build_rolling_summary_prompt(
        agent_name=agent_name,
        previous_summary=previous_summary,
        batch_text=batch_text,
        max_chars=max_chars,
        personality=personality,
        appearance=appearance,
        other_agents=other_agents,
    )
    raw_output: str | None = None
    turn = turn_number or 0
    try:
        response = get_text_completion(prompt, temperature=0.3)
        raw_output = response.raw_response
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
            turn,
            phase="memory_summary",
            prompt=prompt,
            raw_output=response.raw_response,
            result=summary,
            tokens=tokens,
        )
        return summary
    except Exception as exc:
        log_consolidation_error(
            "Rolling summary consolidation failed",
            exc,
            turn_number=turn,
            phase="memory_summary",
            prompt=prompt,
            raw_output=raw_output,
        )
        raise
