"""
types.py

Small shared types for the LLM package.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class LLMResponse:
    """Result of an LLM call for a structured JSON schema."""

    parsed: Any
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    model: Optional[str] = None
    raw_response: Optional[str] = None
