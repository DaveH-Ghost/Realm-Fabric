"""
logger.py

Rich console and file logging helpers for V0.

Per the readiness checklist Section 9:
- Rich, verbose console output on every turn.
- On normal turns: console only (rich format).
- With --log: also write full context to timestamped file in logs/.
- On errors: always to console + file.

Uses 'rich' for pretty output (already a project dependency).
For file logs, writes plain text (or can be extended to JSON).
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional, TextIO

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

console = Console()

# Global state for file logging
_log_file: Optional[TextIO] = None
_log_path: Optional[Path] = None


def setup_file_logging(logs_dir: str = "logs") -> Path:
    """
    Set up file logging. Creates logs/ dir if needed and opens a timestamped file.

    Call this once at startup if --log flag is passed.
    Returns the path to the log file.
    """
    global _log_file, _log_path

    logs_path = Path(logs_dir)
    logs_path.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"run_{timestamp}.log"
    _log_path = logs_path / log_filename
    _log_file = open(_log_path, "w", encoding="utf-8")

    console.print(f"[green]File logging enabled: {_log_path}[/green]")
    return _log_path


def close_file_logging() -> None:
    """Close the log file if open."""
    global _log_file
    if _log_file:
        _log_file.close()
        _log_file = None


def _write_to_file(text: str) -> None:
    """Write text to the log file if file logging is active."""
    if _log_file:
        _log_file.write(text + "\n")
        _log_file.flush()


def log_turn(
    turn_number: int,
    *,
    phase: Optional[str] = None,
    prompt: Optional[str] = None,
    raw_output: Optional[str] = None,
    parsed_turn: Optional[dict] = None,
    result: Optional[str] = None,
    error: Optional[str] = None,
    tokens: Optional[dict] = None,
    always_to_file: bool = False,
) -> None:
    """
    Log a turn with rich console output.

    If file logging is active (or always_to_file), also writes to the log file.

    This provides the "rich, verbose console output on every turn" required by the spec.
    """
    header = f"Turn {turn_number}"
    if phase:
        header += f" [{phase}]"
    if error:
        header += " [ERROR]"

    # File output first (plain text), so it happens even if console has encoding issues in tests
    if _log_file or always_to_file:
        file_text = f"\n=== {header} ===\n"
        if prompt:
            file_text += f"\n--- PROMPT ({len(prompt)} chars) ---\n{prompt}\n"
        if raw_output:
            file_text += f"\n--- RAW OUTPUT ---\n{raw_output}\n"
        if parsed_turn:
            file_text += f"\n--- PARSED ---\n{parsed_turn}\n"
        if result:
            file_text += f"\n--- RESULT ---\n{result}\n"
        if tokens:
            file_text += f"\n--- TOKENS ---\n{tokens}\n"
        if error:
            file_text += f"\n--- ERROR ---\n{error}\n"
        file_text += "=" * 50 + "\n"
        _write_to_file(file_text)

    # Console output (rich)
    console.rule(f"[bold]{header}[/bold]")

    if prompt:
        console.print(Panel(prompt, title="Prompt", border_style="blue", expand=False))

    if raw_output:
        try:
            syntax = Syntax(raw_output, "json", theme="monokai", line_numbers=False)
            console.print(Panel(syntax, title="Raw Model Output", border_style="yellow"))
        except Exception:
            console.print(Panel(raw_output, title="Raw Model Output", border_style="yellow"))

    if parsed_turn:
        title = "Parsed turn" if phase else "Parsed output"
        console.print(Panel(str(parsed_turn), title=title, border_style="green"))

    if result:
        console.print(Panel(result, title="Action Result", border_style="cyan"))

    if tokens:
        token_str = " | ".join(f"{k}: {v}" for k, v in tokens.items())
        console.print(f"[bold]Tokens:[/bold] {token_str}")

    if error:
        console.print(Panel(error, title="ERROR", border_style="red", style="red"))

    console.rule()


def log_error(message: str, exc: Optional[Exception] = None) -> None:
    """Log an error to console (and file if active). Always goes to file."""
    log_turn(
        0,
        error=message + (f"\n{exc}" if exc else ""),
        always_to_file=True,
    )


# Optional: structured JSON logging could be added here later for the "both" option in checklist.