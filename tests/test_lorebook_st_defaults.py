"""ST lorebook entry defaults (V0.5.0)."""

from campaign_rpg_engine.lorebook.st_defaults import (
    ST_ENTRY_DEFAULTS,
    new_st_entry_dict,
    with_st_entry_defaults,
)


def test_with_st_entry_defaults_fills_missing_keys():
    data = with_st_entry_defaults({"uid": 5, "content": "Hello"})
    assert data["uid"] == 5
    assert data["content"] == "Hello"
    assert data["probability"] == 100
    assert data["depth"] == 4
    assert data["position"] == 0
    assert data["vectorized"] is False
    assert data["triggers"] == []
    assert data["scanDepth"] is None
    assert data["displayIndex"] == 5


def test_with_st_entry_defaults_does_not_overwrite_existing():
    data = with_st_entry_defaults({"uid": 1, "probability": 50, "depth": 2})
    assert data["probability"] == 50
    assert data["depth"] == 2


def test_new_st_entry_dict_matches_typical_st_shape():
    entry = new_st_entry_dict(
        42,
        order=100,
        comment="Session note",
        content="Custom lore.",
        keys=["alpha"],
        constant=True,
    )
    assert entry["uid"] == 42
    assert entry["order"] == 100
    assert entry["comment"] == "Session note"
    assert entry["constant"] is True
    assert entry["key"] == ["alpha"]
    assert entry["disable"] is False
    assert entry["addMemo"] is True
    assert entry["useProbability"] is True
    assert "enabled" not in entry
    for key in ST_ENTRY_DEFAULTS:
        assert key in entry


def test_minimal_import_export_gains_st_defaults():
    from campaign_rpg_engine.lorebook import load_lorebook_from_dict

    book = load_lorebook_from_dict(
        {
            "entries": {
                "0": {
                    "uid": 0,
                    "key": ["test"],
                    "content": "Body",
                    "disable": False,
                    "order": 0,
                }
            }
        },
        filename="minimal.lorebook.json",
    )
    exported = book.to_st_export_dict()["entries"]["0"]
    assert exported["probability"] == 100
    assert exported["depth"] == 4
    assert exported["matchCharacterDescription"] is False
    assert exported["content"] == "Body"


def test_real_sample_entry_shape_if_present():
    from pathlib import Path

    from campaign_rpg_engine.lorebook import load_lorebook_from_path

    sample = Path(r"e:\Tavern\Midway\tri-system-universe.lorebook.json")
    if not sample.is_file():
        import pytest

        pytest.skip("sample lorebook not on this machine")
    book = load_lorebook_from_path(sample)
    entry = book.entries[0].to_dict()
    assert entry["probability"] == 100
    assert entry["depth"] == 4
    assert entry["addMemo"] is True
