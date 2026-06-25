"""SillyTavern lorebook import (V0.5.0)."""

import json
from pathlib import Path

import pytest

from src.lorebook import derive_lorebook_id_from_filename, load_lorebook_from_dict

MINIMAL_ST = {
    "entries": {
        "0": {
            "uid": 0,
            "key": ["midway universe"],
            "keysecondary": [],
            "comment": "General world background",
            "content": "Midway setting overview.",
            "constant": True,
            "disable": False,
            "selective": False,
            "selectiveLogic": 0,
            "order": 0,
        },
        "1": {
            "uid": 1,
            "key": ["earth", "sol"],
            "keysecondary": [],
            "comment": "Earth",
            "content": "Earth is crowded.",
            "constant": False,
            "disable": False,
            "selective": False,
            "selectiveLogic": 0,
            "order": 10,
        },
    }
}


def test_derive_lorebook_id_from_filename():
    assert derive_lorebook_id_from_filename("tri-system-universe.lorebook.json") == (
        "tri-system-universe"
    )


def test_load_minimal_st_lorebook():
    book = load_lorebook_from_dict(
        MINIMAL_ST,
        filename="tri-system-universe.lorebook.json",
    )
    assert book.id == "tri-system-universe"
    assert len(book.entries) == 2
    sorted_entries = book.sorted_entries()
    assert sorted_entries[0].uid == 0
    assert sorted_entries[1].order == 10
    assert sorted_entries[0].constant is True
    assert sorted_entries[0].enabled is True


def test_import_uses_disable_only_not_enabled():
    data = {
        "entries": {
            "0": {
                "uid": 0,
                "key": [],
                "content": "Should be on.",
                "constant": False,
                "disable": False,
                "enabled": False,
                "order": 0,
            },
            "1": {
                "uid": 1,
                "key": [],
                "content": "Should be off.",
                "constant": False,
                "disable": True,
                "enabled": True,
                "order": 1,
            },
        }
    }
    book = load_lorebook_from_dict(data, filename="disable-only.lorebook.json")
    by_uid = {entry.uid: entry for entry in book.entries}
    assert by_uid[0].enabled is True
    assert by_uid[1].enabled is False


def test_st_export_dict_matches_load_format():
    book = load_lorebook_from_dict(MINIMAL_ST, filename="demo.lorebook.json")
    book.entries[0].raw["probability"] = 100
    book.entries[0].raw["position"] = 4
    exported = book.to_st_export_dict()
    assert isinstance(exported["entries"], dict)
    entry = exported["entries"]["0"]
    assert entry["disable"] is False
    assert entry["constant"] is True
    assert entry["probability"] == 100
    assert entry["position"] == 4
    assert "enabled" not in entry
    reloaded = load_lorebook_from_dict(exported, filename="demo.lorebook.json")
    assert reloaded.entries[0].content == "Midway setting overview."


def test_load_real_sample_if_present():
    sample = Path(r"e:\Tavern\Midway\tri-system-universe.lorebook.json")
    if not sample.is_file():
        pytest.skip("sample lorebook not on this machine")
    from src.lorebook import load_lorebook_from_path

    book = load_lorebook_from_path(sample)
    assert book.id == "tri-system-universe"
    assert len(book.entries) >= 10


def test_round_trip_dict():
    book = load_lorebook_from_dict(MINIMAL_ST, filename="demo.lorebook.json")
    restored = load_lorebook_from_dict(
        {"entries": {str(i): e.to_dict() for i, e in enumerate(book.entries)}},
        book_id=book.id,
        filename=book.source_filename,
    )
    assert len(restored.entries) == 2
    assert restored.entries[0].content == "Midway setting overview."
