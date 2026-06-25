"""Tests for empty lorebook creation (V0.5.0)."""

from src.lorebook.factory import allocate_lorebook_id, create_empty_lorebook


def test_allocate_lorebook_id_unique():
    assert allocate_lorebook_id(set(), "My Book") == "my-book"
    assert allocate_lorebook_id({"my-book"}, "My Book") == "my-book-2"


def test_create_empty_lorebook_defaults():
    book = create_empty_lorebook()
    assert book.id == "new-lorebook"
    assert book.name == "New lorebook"
    assert book.entries == []
    assert book.source_filename == "new-lorebook.lorebook.json"


def test_create_empty_lorebook_custom_name():
    book = create_empty_lorebook(name="Tavern Notes", existing_ids={"tavern-notes"})
    assert book.id == "tavern-notes-2"
    assert book.name == "Tavern Notes"
