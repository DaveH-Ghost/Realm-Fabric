"""Keyword matching and lorebook prompt rendering (V0.5.0)."""

from __future__ import annotations

from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area
from campaign_rpg_engine.lorebook.models import DEFAULT_LOREBOOK_CHAR_BUDGET, Lorebook, LoreEntry
from campaign_rpg_engine.lorebook.scan_config import LorebookScanConfig


def build_scan_corpus(
    *,
    agent: Agent,
    area: Area,
    memory_text: str = "",
    passive_vision: str = "",
    scan_config: LorebookScanConfig | None = None,
) -> str:
    cfg = scan_config or LorebookScanConfig()
    parts: list[str] = []
    if cfg.agent_name and agent.name:
        parts.append(agent.name)
    if cfg.agent_personality and agent.personality:
        parts.append(agent.personality)
    if cfg.agent_description and agent.description:
        parts.append(agent.description)
    if cfg.area_description and area.area_description:
        parts.append(area.area_description)
    if cfg.memory and memory_text:
        parts.append(memory_text)
    if cfg.passive_vision and passive_vision:
        parts.append(passive_vision)
    if cfg.recent_events:
        for event in area.recent_events:
            if event.text:
                parts.append(event.text)
    return "\n".join(parts)


def _case_sensitive(entry: LoreEntry) -> bool:
    raw = entry.raw.get("caseSensitive")
    if raw is None:
        return False
    return bool(raw)


def _text_contains(haystack: str, needle: str, *, case_sensitive: bool) -> bool:
    if not needle:
        return False
    if case_sensitive:
        return needle in haystack
    return needle.lower() in haystack.lower()


def _any_key_matches(keys: list[str], corpus: str, *, case_sensitive: bool) -> bool:
    return any(_text_contains(corpus, key, case_sensitive=case_sensitive) for key in keys)


def _entry_matches(entry: LoreEntry, corpus: str) -> bool:
    if not entry.enabled:
        return False
    if entry.constant:
        return True
    if not entry.keys:
        return False
    case_sensitive = _case_sensitive(entry)
    primary = _any_key_matches(entry.keys, corpus, case_sensitive=case_sensitive)
    if not entry.selective:
        return primary
    secondary = _any_key_matches(
        entry.keys_secondary, corpus, case_sensitive=case_sensitive
    )
    if entry.selective_logic == 3:
        return primary or secondary
    return primary and secondary


def match_lorebook_entries(
    book: Lorebook,
    corpus: str,
    *,
    char_budget: int = DEFAULT_LOREBOOK_CHAR_BUDGET,
) -> list[LoreEntry]:
    matched: list[LoreEntry] = []
    used = 0
    for entry in book.sorted_entries():
        if not _entry_matches(entry, corpus):
            continue
        content = entry.content.strip()
        if not content:
            continue
        extra = len(content) + (2 if matched else 0)
        if not entry.ignore_budget and used + extra > char_budget:
            break
        if not entry.ignore_budget:
            used += extra
        matched.append(entry)
    return matched


def render_lorebook(
    book: Lorebook,
    corpus: str,
    *,
    char_budget: int = DEFAULT_LOREBOOK_CHAR_BUDGET,
) -> str:
    matched = match_lorebook_entries(book, corpus, char_budget=char_budget)
    if not matched:
        return ""
    body = "\n\n".join(entry.content.strip() for entry in matched)
    return f"World info:\n{body}"
