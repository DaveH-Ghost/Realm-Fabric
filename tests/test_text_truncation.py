"""Sentence-aware truncation (V0.4.1a)."""

from src.llm.schemas import AgentCompoundTurn
from src.llm.text_truncation import (
    REASONING_MAX_CHARS,
    SPEAK_MAX_CHARS,
    count_sentences,
    split_sentences_with_spans,
    truncate_at_sentence_boundary,
)


def test_count_sentences_ellipsis():
    assert count_sentences("Hi! Wait... really?") == 2


def test_split_preserves_ellipsis_inside_sentence():
    spans = split_sentences_with_spans("Wait... really?")
    assert len(spans) == 1
    assert "..." in "Wait... really?"[spans[0][0] : spans[0][1]]


def test_truncate_under_budget_unchanged():
    text = "Hello there."
    assert truncate_at_sentence_boundary(text, 500) == text


def test_truncate_keeps_sentence_that_starts_before_budget_even_if_long():
    text = "A" * 600
    assert truncate_at_sentence_boundary(text, 500) == text


def test_truncate_drops_sentences_starting_at_or_after_budget():
    first = "A" * 498 + ". "
    second = "B" * 100
    text = first + second
    spans = split_sentences_with_spans(text)
    assert len(spans) == 2
    assert spans[1][0] >= 500

    result = truncate_at_sentence_boundary(text, 500)
    assert result == "A" * 498 + "."
    assert "B" not in result


def test_truncate_keeps_second_sentence_when_it_starts_before_budget():
    first = "A" * 470 + ". "
    second = "B" * 80 + "."
    text = first + second
    assert split_sentences_with_spans(text)[1][0] < 500

    result = truncate_at_sentence_boundary(text, 500)
    assert result.endswith(".")
    assert "B" in result
    assert len(result) > 500


def test_truncate_reasoning_via_schema():
    long_reasoning = "x" * 450
    turn = AgentCompoundTurn(reasoning=long_reasoning, action="none")
    assert len(turn.reasoning) == 450


def test_truncate_reasoning_drops_late_sentences():
    first = "a" * 398 + ". "
    second = "b" * 100
    reasoning = first + second
    turn = AgentCompoundTurn(reasoning=reasoning, action="none")
    assert turn.reasoning == "a" * 398 + "."
    assert "b" not in turn.reasoning


def test_truncate_speak_via_schema():
    text = "A" * 501
    turn = AgentCompoundTurn(reasoning="ok", action="none", say=text)
    assert len(turn.say) == 501


def test_truncate_speak_many_sentences_no_sentence_cap():
    parts = [f"Word{i} " + "x" * 40 + "." for i in range(12)]
    text = " ".join(parts)
    assert count_sentences(text) == 12
    assert len(text) > SPEAK_MAX_CHARS
    result = truncate_at_sentence_boundary(text, SPEAK_MAX_CHARS)
    assert count_sentences(result) < 12
    assert len(result) < len(text)


def test_speak_at_budget_unchanged():
    text = "A" * 400
    turn = AgentCompoundTurn(reasoning="x", action="none", say=text)
    assert len(turn.say) == 400


def test_reasoning_exactly_at_budget():
    text = "A" * REASONING_MAX_CHARS
    turn = AgentCompoundTurn(reasoning=text, action="none")
    assert len(turn.reasoning) == REASONING_MAX_CHARS
