"""LLM affinity consolidation (Call B) — window-only relationship updates."""

from __future__ import annotations

import json
import re
from typing import Any

from campaign_rpg_engine.llm.client import get_text_completion
from campaign_rpg_engine.log_utils import log_turn
from campaign_rpg_engine.memory_modules.affinity_ladder import (
    DEFAULT_RELATIONSHIP_SUMMARY_MAX_CHARS,
    minus_guidance,
    plus_guidance,
)


def build_affinity_update_prompt(
    *,
    agent_name: str,
    batch_text: str,
    candidates: list[dict[str, Any]],
    max_summary_chars: int = DEFAULT_RELATIONSHIP_SUMMARY_MAX_CHARS,
) -> str:
    blocks: list[str] = []
    for entry in candidates:
        name = str(entry.get("name") or entry["agent_id"])
        score = int(entry.get("score", 0))
        prior = str(entry.get("summary") or "").strip() or "(none yet)"
        blocks.append(
            f"""### {name} (id={entry["agent_id"]})
Current affinity: {score}
Prior relationship summary: {prior}
When to emit +1: {plus_guidance(score, name)}
When to emit -1: {minus_guidance(score, name)}"""
        )
    candidate_block = "\n\n".join(blocks)
    return f"""You update relationship affinities for {agent_name} in a grid-area RPG simulation.

You receive ONLY the recent turn window below (not any long-term rolling chronicle).
Award affinity deltas ONLY from events in that window. Use prior relationship summaries
for continuity of the short blurb — do NOT re-score old history that is not reflected
in this window. Prefer delta 0 when nothing relationship-relevant happened.

For each listed agent, return an updated short relationship summary (full replacement)
and a delta of -1, 0, or +1 following the per-score guidance.

Rules:
- Score deltas must come from THIS WINDOW only.
- Relationship summary: 1–2 short sentences, at most {max_summary_chars} characters,
  concrete facts (“She covered for you on watch”), not adjective stacks.
- Do not invent agents or events.
- At affinity 10 never emit +1; at -10 never emit -1.
- Respond with ONLY a JSON array (no markdown fences). Each item:
  {{"agent_id": "...", "name": "...", "delta": -1|0|1, "summary": "..."}}
- Include every listed candidate exactly once.

Candidates:
{candidate_block}

Turn window:
{batch_text}
""".strip()


def _extract_json_array(text: str) -> list[Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", cleaned)
        if not match:
            raise
        data = json.loads(match.group(0))
    if not isinstance(data, list):
        raise ValueError("Affinity consolidator must return a JSON array")
    return data


def parse_and_validate_affinity_updates(
    raw: str,
    *,
    candidates: list[dict[str, Any]],
    max_summary_chars: int = DEFAULT_RELATIONSHIP_SUMMARY_MAX_CHARS,
) -> list[dict[str, Any]]:
    by_id = {str(c["agent_id"]): c for c in candidates}
    rows = _extract_json_array(raw)
    if len(rows) != len(candidates):
        raise ValueError(
            f"Affinity consolidator returned {len(rows)} rows; expected {len(candidates)}"
        )
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Affinity update rows must be objects")
        agent_id = str(row.get("agent_id", "")).strip()
        if agent_id not in by_id:
            raise ValueError(f"Unknown affinity agent_id {agent_id!r}")
        if agent_id in seen:
            raise ValueError(f"Duplicate affinity agent_id {agent_id!r}")
        seen.add(agent_id)
        try:
            delta = int(row.get("delta", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid delta for {agent_id}") from exc
        if delta not in (-1, 0, 1):
            raise ValueError(f"Delta for {agent_id} must be -1, 0, or 1 (got {delta})")
        score = int(by_id[agent_id].get("score", 0))
        if score >= 10 and delta == 1:
            raise ValueError(f"Cannot +1 affinity for {agent_id} at MAX")
        if score <= -10 and delta == -1:
            raise ValueError(f"Cannot -1 affinity for {agent_id} at MIN")
        summary = str(row.get("summary", "")).strip()
        if len(summary) > max_summary_chars:
            summary = summary[: max_summary_chars - 1] + "…"
        name = str(row.get("name") or by_id[agent_id].get("name") or agent_id)
        out.append(
            {
                "agent_id": agent_id,
                "name": name,
                "delta": delta,
                "summary": summary,
            }
        )
    if seen != set(by_id):
        missing = set(by_id) - seen
        raise ValueError(f"Missing affinity updates for: {sorted(missing)}")
    return out


def generate_affinity_updates(
    *,
    agent_name: str,
    batch_text: str,
    candidates: list[dict[str, Any]],
    max_summary_chars: int = DEFAULT_RELATIONSHIP_SUMMARY_MAX_CHARS,
    turn_number: int | None = None,
) -> list[dict[str, Any]]:
    """Call the LLM for affinity deltas + relationship blurbs (Call B)."""
    if not candidates:
        return []
    prompt = build_affinity_update_prompt(
        agent_name=agent_name,
        batch_text=batch_text,
        candidates=candidates,
        max_summary_chars=max_summary_chars,
    )
    response = get_text_completion(prompt, temperature=0.2)
    raw = str(response.parsed).strip()
    if not raw:
        raise RuntimeError("LLM returned empty affinity update")
    updates = parse_and_validate_affinity_updates(
        raw,
        candidates=candidates,
        max_summary_chars=max_summary_chars,
    )

    tokens = None
    if response.total_tokens is not None:
        tokens = {
            "prompt": response.prompt_tokens,
            "completion": response.completion_tokens,
            "total": response.total_tokens,
        }
    log_turn(
        turn_number or 0,
        phase="memory_affinity",
        prompt=prompt,
        raw_output=response.raw_response,
        result=json.dumps(updates),
        tokens=tokens,
    )
    return updates
