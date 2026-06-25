"""Read-only lorebook listing for CLI."""

from __future__ import annotations

from src.lorebook.models import Lorebook


def format_lorebooks_list(books: list[Lorebook]) -> str:
    if not books:
        return "No lorebooks loaded. Use load-lorebook <path> or realm-studio Lorebooks tab."
    lines = ["Loaded lorebooks:"]
    for book in sorted(books, key=lambda item: item.id):
        lines.append(
            f"  - {book.id}: {book.name} ({len(book.entries)} entries)"
            + (f" [{book.source_filename}]" if book.source_filename else "")
        )
    return "\n".join(lines)
