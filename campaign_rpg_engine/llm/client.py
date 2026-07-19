"""
client.py

LLM client for OpenAI-compatible providers (OpenRouter, Featherless).
"""

from __future__ import annotations

import os
from typing import TypeVar

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from campaign_rpg_engine.llm.token_estimate import prompt_exceeds_max_input
from campaign_rpg_engine.llm.types import LLMResponse


def _load_environment() -> None:
    load_dotenv()
    load_dotenv(".env.local", override=True)


_load_environment()

PROVIDER_OPENROUTER = "openrouter"
PROVIDER_FEATHERLESS = "featherless"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
FEATHERLESS_BASE_URL = "https://api.featherless.ai/v1"

DEFAULT_OPENROUTER_MODEL = "deepseek/deepseek-v4-flash"
DEFAULT_FEATHERLESS_MODEL = "deepseek-ai/DeepSeek-V4-Flash"

# Back-compat alias used by older call sites / docs.
DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL)

T = TypeVar("T", bound=BaseModel)


class LLMParseError(ValueError):
    """Raised when LLM output is not valid JSON or fails schema validation."""

    def __init__(self, message: str, *, raw_response: str | None = None):
        super().__init__(message)
        self.raw_response = raw_response


class PromptTooLargeError(RuntimeError):
    """Raised when the estimated prompt exceeds ``LLM_MAX_INPUT_TOKENS``."""

    def __init__(self, estimate: int, limit: int):
        self.estimate = estimate
        self.limit = limit
        super().__init__(
            f"Prompt too large: ~{estimate} estimated input tokens exceeds "
            f"limit of {limit} (LLM_MAX_INPUT_TOKENS). Shorten memory, lorebooks, "
            f"or raise the limit in settings / .env."
        )


def get_llm_provider() -> str:
    """Return active provider id (``openrouter`` or ``featherless``)."""
    raw = (os.environ.get("LLM_PROVIDER") or PROVIDER_OPENROUTER).strip().lower()
    if raw in (PROVIDER_OPENROUTER, PROVIDER_FEATHERLESS):
        return raw
    return PROVIDER_OPENROUTER


def resolve_llm_model(explicit: str | None = None) -> str:
    """Resolve model id for the active provider (or *explicit* override)."""
    if explicit and explicit.strip():
        return explicit.strip()
    provider = get_llm_provider()
    if provider == PROVIDER_FEATHERLESS:
        return os.getenv("FEATHERLESS_MODEL", "").strip() or DEFAULT_FEATHERLESS_MODEL
    return os.getenv("OPENROUTER_MODEL", "").strip() or DEFAULT_OPENROUTER_MODEL


def _provider_missing_key_message(provider: str, key_env: str, docs_url: str) -> str:
    return (
        f"{key_env} not found (LLM_PROVIDER={provider}).\n\n"
        "How to fix (simple steps):\n"
        "1. In PowerShell, run:\n"
        "   copy .env.example .env\n"
        "2. Open the new .env file and set LLM_PROVIDER plus the matching API key.\n"
        "3. (Optional) You can also create a .env.local file for your personal settings.\n"
        "4. Or use Studio Settings (gear) for this process only.\n\n"
        f"Get a key here: {docs_url}"
    )


def get_llm_client() -> OpenAI:
    """Return an OpenAI client for the configured provider."""
    provider = get_llm_provider()
    if provider == PROVIDER_FEATHERLESS:
        api_key = (os.getenv("FEATHERLESS_API_KEY") or "").strip()
        if not api_key:
            raise RuntimeError(
                _provider_missing_key_message(
                    PROVIDER_FEATHERLESS,
                    "FEATHERLESS_API_KEY",
                    "https://featherless.ai/account/api-keys",
                )
            )
        return OpenAI(
            base_url=FEATHERLESS_BASE_URL,
            api_key=api_key,
        )

    api_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError(
            _provider_missing_key_message(
                PROVIDER_OPENROUTER,
                "OPENROUTER_API_KEY",
                "https://openrouter.ai/",
            )
        )
    return OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=api_key,
    )


def _assert_prompt_within_budget(prompt: str) -> None:
    over, estimate, limit = prompt_exceeds_max_input(prompt)
    if over:
        raise PromptTooLargeError(estimate, limit)


def _strip_json_wrapper(content: str) -> str:
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content
        if content.endswith("```"):
            content = content[:-3].strip()
    return content


def _looks_like_missing_leading_brace(content: str) -> bool:
    """Featherless DeepSeek Flash often returns object bodies without the opening ``{``."""
    text = content.strip()
    return bool(text) and not text.startswith("{") and text.endswith("}")


def _parse_structured_json(schema: type[T], content: str) -> tuple[T, str]:
    """Parse JSON into *schema*; retry once with a leading ``{`` if needed.

    Returns ``(parsed, content_used)``. On final failure raises ``LLMParseError``
    with the original *content* as ``raw_response``.
    """
    try:
        return schema.model_validate_json(content), content
    except ValidationError as first_exc:
        if not _looks_like_missing_leading_brace(content):
            raise LLMParseError(
                f"ERR:INVALID_JSON: {first_exc}",
                raw_response=content,
            ) from first_exc
        repaired = "{" + content.lstrip()
        try:
            return schema.model_validate_json(repaired), repaired
        except ValidationError as second_exc:
            raise LLMParseError(
                f"ERR:INVALID_JSON: {second_exc}",
                raw_response=content,
            ) from second_exc


def get_structured_turn(
    prompt: str,
    schema: type[T],
    model: str | None = None,
    temperature: float = 0.7,
) -> LLMResponse:
    """Send prompt to LLM and parse JSON into the given Pydantic schema."""
    _assert_prompt_within_budget(prompt)
    client = get_llm_client()
    model = resolve_llm_model(model)

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
    parsed, content = _parse_structured_json(schema, content)

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
    model: str | None = None,
    temperature: float = 0.7,
) -> LLMResponse:
    """Send prompt to LLM; entire message content is the response text."""
    _assert_prompt_within_budget(prompt)
    client = get_llm_client()
    model = resolve_llm_model(model)

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
