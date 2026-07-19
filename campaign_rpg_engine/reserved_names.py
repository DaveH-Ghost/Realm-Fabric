"""
Reserved command names for agent display-name validation.

Agent names are matched case-insensitively against this frozen set so they
cannot collide with legacy stepper-style command tokens.
"""

from __future__ import annotations

# Former ManualStepper do_* handlers (hyphenated) plus cmd help alias.
_RESERVED_COMMAND_NAMES: frozenset[str] = frozenset(
    {
        "?",
        "run",
        "switch",
        "vision",
        "prompt",
        "state",
        "objects",
        "handlers",
        "effects",
        "memory-modules",
        "load-lorebook",
        "lorebooks",
        "agents",
        "areas",
        "active-area",
        "create-area",
        "edit-area",
        "delete-area",
        "list",
        "create-object",
        "emit-event",
        "edit-object",
        "delete-object",
        "create-agent",
        "edit-agent",
        "delete-agent",
        "fewshots",
        "step-compound",
        "step-nav",
        "step-action",
        "help",
        "export-session",
        "import-session",
        "quit",
        "exit",
    }
)


def get_reserved_stepper_commands() -> frozenset[str]:
    """Return reserved names (kept for compatibility with pre-1.0 imports)."""
    return _RESERVED_COMMAND_NAMES


def get_reserved_command_names() -> frozenset[str]:
    return _RESERVED_COMMAND_NAMES


def _name_variants(name: str) -> set[str]:
    n = name.strip().lower()
    return {n, n.replace("-", "_"), n.replace("_", "-")}


def agent_name_conflicts_with_commands(name: str) -> bool:
    """Return True if name would collide with a reserved command (case-insensitive)."""
    variants = _name_variants(name)
    return any(variants & _name_variants(reserved) for reserved in _RESERVED_COMMAND_NAMES)


def reserved_agent_name_message(name: str) -> str:
    return (
        f"Agent name '{name}' conflicts with a reserved command name. "
        f"Choose a different display name."
    )
