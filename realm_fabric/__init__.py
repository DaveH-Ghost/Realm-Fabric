"""
realm_fabric — public engine API for Realm-Fabric (V0.4.4).

Downstream projects should import from this package. Modules under ``src.*``
remain importable for the CLI and tests but are not guaranteed stable.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from src.agent import Agent
from src.area import Area, GridBounds, create_area, create_initial_area
from src.game_profile import GameProfile, default_compound_profile, load_profile
from src.llm.prompt_context import PromptContext, build_prompt_context
from src.llm.schemas import AgentCompoundTurn
from src.object import Object
from src.session import CommandResult, Session, SessionResult, TurnResult
from src.simulation import run_compound_turn
from src.snapshot import DEFAULT_AREA_ID, build_area_snapshot, build_session_snapshot

__all__ = [
    "__version__",
    "Agent",
    "AgentCompoundTurn",
    "Area",
    "CommandResult",
    "GameProfile",
    "GridBounds",
    "Object",
    "PromptContext",
    "Session",
    "SessionResult",
    "TurnResult",
    "build_area_snapshot",
    "build_session_snapshot",
    "DEFAULT_AREA_ID",
    "build_prompt_context",
    "create_area",
    "create_initial_area",
    "default_compound_profile",
    "load_profile",
    "run_compound_turn",
]

_ROOT = Path(__file__).resolve().parent.parent


def _read_version() -> str:
    pyproject_version = tomllib.loads(
        (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]
    try:
        from importlib.metadata import version as _pkg_version

        installed = _pkg_version("realm-fabric")
        if installed == pyproject_version:
            return installed
    except Exception:
        pass
    return pyproject_version


__version__ = _read_version()
