"""Lorebook scan source configuration (V0.5.0)."""

from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area
from campaign_rpg_engine.lorebook.matcher import build_scan_corpus
from campaign_rpg_engine.lorebook.scan_config import LorebookScanConfig, describe_scan_sources
from campaign_rpg_engine.session import Session


def test_passive_vision_included_in_corpus_by_default():
    agent = Agent(id="a1", name="Explorer", personality="", position=(1, 1))
    area = Area(area_description="A quiet room.")
    corpus = build_scan_corpus(
        agent=agent,
        area=area,
        passive_vision="Ball (obj_ball_01) at 2,2",
    )
    assert "Ball (obj_ball_01)" in corpus


def test_passive_vision_can_be_disabled():
    agent = Agent(id="a1", name="Explorer", personality="", position=(1, 1))
    area = Area(area_description="A quiet room.")
    cfg = LorebookScanConfig(passive_vision=False, agent_name=False)
    corpus = build_scan_corpus(
        agent=agent,
        area=area,
        passive_vision="Ball (obj_ball_01) at 2,2",
        scan_config=cfg,
    )
    assert "Ball" not in corpus
    assert "quiet room" in corpus


def test_describe_scan_sources_lists_all_sources():
    agent = Agent(id="a1", name="Ada", personality="Curious", description="Tall.", position=(0, 0))
    area = Area(area_description="Hallway")
    rows = describe_scan_sources(
        agent=agent,
        area=area,
        memory_text="Recent memory.",
        passive_vision="You see a sign.",
        scan_config=LorebookScanConfig(),
    )
    ids = {row["id"] for row in rows}
    assert ids == {
        "agent_name",
        "agent_personality",
        "agent_description",
        "area_description",
        "memory",
        "passive_vision",
        "recent_events",
    }
    passive = next(row for row in rows if row["id"] == "passive_vision")
    assert "sign" in passive["preview"]


def test_scan_config_round_trip_in_snapshot():
    session = Session.from_default()
    session.lorebook_scan_config = LorebookScanConfig(
        passive_vision=True,
        memory=False,
    )
    from campaign_rpg_engine.session_persistence import build_save_snapshot, load_session_from_snapshot

    snapshot = build_save_snapshot(session)
    loaded = load_session_from_snapshot(snapshot)
    assert loaded.lorebook_scan_config.passive_vision is True
    assert loaded.lorebook_scan_config.memory is False
