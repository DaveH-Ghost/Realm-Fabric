"""Lorebook keyword matching (V0.5.0)."""

from src.agent import Agent
from src.area import Area
from src.lorebook import load_lorebook_from_dict, match_lorebook_entries, render_lorebook
from src.lorebook.matcher import build_scan_corpus
from src.lorebook.models import LoreEntry, Lorebook

_BOOK = load_lorebook_from_dict(
    {
        "entries": {
            "0": {
                "uid": 0,
                "key": [],
                "content": "Always here.",
                "constant": True,
                "disable": False,
                "order": 0,
            },
            "1": {
                "uid": 1,
                "key": ["earth"],
                "content": "Earth detail.",
                "constant": False,
                "disable": False,
                "order": 10,
            },
            "2": {
                "uid": 2,
                "key": ["mars"],
                "content": "Mars detail.",
                "constant": False,
                "disable": True,
                "order": 20,
            },
        }
    },
    book_id="test",
)


def _corpus(text: str) -> str:
    agent = Agent(id="a1", name="Explorer", personality="", position=(1, 1))
    area = Area(area_description=text)
    return build_scan_corpus(agent=agent, area=area, memory_text="")


def test_constant_entry_always_matches():
    matched = match_lorebook_entries(_BOOK, _corpus("quiet room"))
    assert any(entry.uid == 0 for entry in matched)


def test_keyword_entry_matches_corpus():
    matched = match_lorebook_entries(_BOOK, _corpus("back on earth again"))
    ids = {entry.uid for entry in matched}
    assert 0 in ids
    assert 1 in ids
    assert 2 not in ids


def test_disabled_entry_skipped():
    matched = match_lorebook_entries(_BOOK, _corpus("mission to mars"))
    assert all(entry.uid != 2 for entry in matched)


def test_selective_requires_primary_and_secondary():
    book = Lorebook(
        id="sel",
        name="sel",
        entries=[
            LoreEntry(
                uid=1,
                keys=["alpha"],
                keys_secondary=["beta"],
                selective=True,
                selective_logic=0,
                content="Both keys.",
                order=0,
            )
        ],
    )
    assert not match_lorebook_entries(book, "alpha only")
    assert match_lorebook_entries(book, "alpha and beta team")


def test_char_budget_limits_entries():
    book = Lorebook(
        id="budget",
        name="budget",
        entries=[
            LoreEntry(uid=0, constant=True, content="A" * 100, order=0),
            LoreEntry(uid=1, constant=True, content="B" * 100, order=1, ignore_budget=False),
            LoreEntry(uid=2, constant=True, content="C" * 100, order=2),
        ],
    )
    matched = match_lorebook_entries(book, "", char_budget=150)
    assert len(matched) == 1


def test_render_includes_world_info_header():
    text = render_lorebook(_BOOK, _corpus("earth"))
    assert text.startswith("World info:")
    assert "Always here." in text
    assert "Earth detail." in text
