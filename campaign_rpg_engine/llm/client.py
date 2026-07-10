"""
client.py

LLM client for talking to models via OpenRouter (OpenAI-compatible).
"""
from __future__ import annotations

import os
from typing import Optional, Type, TypeVar

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from campaign_rpg_engine.llm.types import LLMResponse


def _load_environment() -> None:
    load_dotenv()
    load_dotenv(".env.local", override=True)


_load_environment()

DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash")

T = TypeVar("T", bound=BaseModel)


class LLMParseError(ValueError):
    """Raised when LLM output is not valid JSON or fails schema validation."""


def get_llm_client() -> OpenAI:
    """Return an OpenAI client configured for OpenRouter."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY not found.\n\n"
            "How to fix (simple steps):\n"
            "1. In PowerShell, run:\n"
            "   copy .env.example .env\n"
            "2. Open the new .env file and replace the placeholder with your real key.\n"
            "3. (Optional) You can also create a .env.local file for your personal settings.\n\n"
            "Get a key here: https://openrouter.ai/"
        )

    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )


def _strip_json_wrapper(content: str) -> str:
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content
        if content.endswith("```"):
            content = content[:-3].strip()
    return content


def get_structured_turn(
    prompt: str,
    schema: Type[T],
    model: Optional[str] = None,
    temperature: float = 0.7,
) -> LLMResponse:
    """Send prompt to LLM and parse JSON into the given Pydantic schema."""
    client = get_llm_client()
    model = model or os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("LLM returned empty content")

    content = _strip_json_wrapper(content)
    try:
        parsed = schema.model_validate_json(content)
    except ValidationError as exc:
        raise LLMParseError(f"ERR:INVALID_JSON: {exc}") from exc

    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
    completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
    total_tokens = getattr(usage, "total_tokens", None) if usage else None

    return LLMResponse(
        parsed=parsed,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        model=model,
        raw_response=content,
    )


def get_text_completion(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
) -> LLMResponse:
    """Send prompt to LLM; entire message content is the response text."""
    client = get_llm_client()
    model = model or os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )

    content = response.choices[0].message.content
    if not content or not content.strip():
        raise RuntimeError("LLM returned empty content")

    text = content.strip()
    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
    completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
    total_tokens = getattr(usage, "total_tokens", None) if usage else None

    return LLMResponse(
        parsed=text,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        model=model,
        raw_response=text,
    )


def get_compound_turn(prompt: str, **kwargs) -> LLMResponse:
    from campaign_rpg_engine.llm.schemas import AgentCompoundTurn

    return get_structured_turn(prompt, AgentCompoundTurn, **kwargs)
