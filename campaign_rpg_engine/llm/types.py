"""
types.py

Small shared types for the LLM package.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    """Result of an LLM call for a structured JSON schema."""

    parsed: Any
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    model: str | None = None
    raw_response: str | None = None
