"""Robust detection of provider concurrency-limit errors."""

from __future__ import annotations

from campaign_rpg_engine.llm.client import (
    ConcurrencyLimitError,
    is_concurrency_limit_error,
)


class _FakeApiError(Exception):
    def __init__(self, message, *, status_code=None, code=None, body=None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.body = body


def test_featherless_style_429_body_is_concurrency():
    exc = _FakeApiError(
        "Error code: 429",
        status_code=429,
        body={
            "error": {
                "message": (
                    "Concurrency limit exceeded. Active concurrent requests: 4 units. "
                    "This request requires: 4 units."
                ),
                "type": "invalid_request_error",
                "code": "concurrency_limit_exceeded",
            }
        },
    )
    assert is_concurrency_limit_error(exc) is True


def test_code_alone_is_enough():
    exc = _FakeApiError(
        "rate limited",
        status_code=429,
        body={"error": {"message": "busy", "code": "concurrency_limit_exceeded"}},
    )
    assert is_concurrency_limit_error(exc) is True


def test_generic_429_without_concurrency_signal_is_not_concurrency():
    exc = _FakeApiError(
        "Error code: 429 - rate limit reached, try again later",
        status_code=429,
        body={"error": {"message": "rate limit reached, try again later", "code": "rate_limit"}},
    )
    assert is_concurrency_limit_error(exc) is False


def test_message_with_concurrent_and_429_without_status_attr():
    exc = Exception(
        "Error code: 429 - {'error': {'message': 'Concurrency limit exceeded', "
        "'code': 'concurrency_limit_exceeded'}}"
    )
    assert is_concurrency_limit_error(exc) is True


def test_concurrency_limit_error_instance():
    assert is_concurrency_limit_error(ConcurrencyLimitError()) is True
