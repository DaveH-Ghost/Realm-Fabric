"""
Sentence-aware text truncation for LLM turn fields (V0.4.1a).

Models often exceed character budgets; trim at sentence boundaries instead of
rejecting the turn. Ellipsis runs (...) are not sentence boundaries.
"""

from __future__ import annotations

import re

REASONING_MAX_CHARS = 400
SPEAK_MAX_CHARS = 500

_ELLIPSIS_MASK = "\uffff"


def _mask_ellipsis_runs(text: str) -> str:
    """Replace runs of 2+ dots so they do not act as sentence terminators."""
    chars = list(text)
    i = 0
    n = len(chars)
    while i < n:
        if chars[i] == ".":
            j = i
            while j < n and chars[j] == ".":
                j += 1
            if j - i >= 2:
                for k in range(i, j):
                    chars[k] = _ELLIPSIS_MASK
            i = j
        else:
            i += 1
    return "".join(chars)


def _trim_span(text: str, start: int, end: int) -> tuple[int, int] | None:
    s = start
    while s < end and text[s].isspace():
        s += 1
    e = end
    while e > s and text[e - 1].isspace():
        e -= 1
    if e <= s:
        return None
    return s, e


def split_sentences_with_spans(text: str) -> list[tuple[int, int]]:
    """
    Return ``(start, end)`` half-open spans for each sentence in *text*.

    Sentence boundaries are ``.!?`` runs followed by optional whitespace.
    Ellipsis (``...``) is preserved inside a sentence.
    """
    if not text.strip():
        return []

    masked = _mask_ellipsis_runs(text)
    spans: list[tuple[int, int]] = []
    start = 0
    for match in re.finditer(r"[.!?]+\s*", masked):
        punct_end = match.start()
        while punct_end < match.end() and text[punct_end] in ".!?":
            punct_end += 1
        span = _trim_span(text, start, punct_end)
        if span:
            spans.append(span)
        start = match.end()

    span = _trim_span(text, start, len(text))
    if span:
        spans.append(span)

    if not spans:
        trimmed = _trim_span(text, 0, len(text))
        if trimmed:
            return [trimmed]
    return spans


def count_sentences(text: str) -> int:
    """Count sentences; ellipsis runs are not sentence boundaries."""
    return len(split_sentences_with_spans(text.strip()))


def truncate_at_sentence_boundary(text: str, max_chars: int) -> str:
    """
    Trim *text* to fit a character budget without cutting mid-sentence.

    Keep every sentence whose start index (0-based, on stripped text) is
    strictly less than *max_chars*. Drop later sentences. If a kept sentence
    extends past the budget, it is kept whole.
    """
    if max_chars <= 0:
        return ""
    stripped = text.strip()
    if not stripped:
        return stripped
    if len(stripped) <= max_chars:
        return stripped

    spans = split_sentences_with_spans(stripped)
    if not spans:
        return stripped

    kept = [span for span in spans if span[0] < max_chars]
    if not kept:
        return ""

    return stripped[kept[0][0] : kept[-1][1]]
