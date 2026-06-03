"""
client.py

LLM client for talking to models via OpenRouter (OpenAI-compatible).

Currently configured for DeepSeek models.

Usage:
    from src.llm.client import get_next_action
    from src.llm.prompt import build_prompt

    prompt = build_prompt(agent, world)
    llm_resp = get_next_action(prompt)
    turn = llm_resp.turn
    print(f"Tokens: input={llm_resp.prompt_tokens}, output={llm_resp.completion_tokens}")
"""

import os
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

from src.llm.schemas import AgentTurn
from src.llm.types import LLMResponse


def _load_environment() -> None:
    """
    Load environment variables from .env files.

    Loading order (later files override earlier ones):
    1. .env                 - base configuration (commit .env.example instead, never real secrets)
    2. .env.local           - your local overrides (this file should be gitignored)

    You can have multiple .env files for different purposes:
    - .env                  → shared base settings for the team
    - .env.local            → your personal machine overrides (gitignored)
    - .env.development      → development-specific values
    - .env.production       → production values

    Example of loading a specific one:
        load_dotenv(".env.production", override=True)

    In this project we automatically load .env + .env.local when the LLM client is first used.
    """
    # Load base .env first (if it exists)
    load_dotenv()

    # Then load .env.local which can override values for local development
    # (this file should be in .gitignore - it already is in this project)
    load_dotenv(".env.local", override=True)


_load_environment()

DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash")


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
        # You can add extra headers for OpenRouter if desired, e.g. for rankings
    )


def get_next_action(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
) -> LLMResponse:
    """
    Send the prompt to the LLM and return a parsed AgentTurn plus usage info.

    The prompt should already contain instructions to output valid JSON
    matching the AgentTurn schema (see prompt.py).

    Returns an LLMResponse which includes:
    - the parsed turn
    - token usage (prompt_tokens = input, completion_tokens = output)
      when the provider returns it (OpenRouter/DeepSeek usually do).
    """
    client = get_llm_client()
    model = model or DEFAULT_MODEL

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        temperature=temperature,
        # Many models on OpenRouter respect this for structured output
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("LLM returned empty content")

    # The prompt tells the model to output pure JSON, but some models
    # still wrap it in ```json ... ```. Strip common wrappers.
    content = content.strip()
    if content.startswith("```"):
        # Remove ```json or ``` and trailing ```
        content = content.split("\n", 1)[1] if "\n" in content else content
        if content.endswith("```"):
            content = content[:-3].strip()

    turn = AgentTurn.model_validate_json(content)

    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
    completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
    total_tokens = getattr(usage, "total_tokens", None) if usage else None

    return LLMResponse(
        turn=turn,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        model=model,
        raw_response=content,
    )
