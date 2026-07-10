"""private_data on agents and objects (app-owned, not LLM/CLI)."""

from campaign_rpg_engine.area import Area, GridBounds
from campaign_rpg_engine.area_edit import create_object_from_args
from campaign_rpg_engine.session import Session
from campaign_rpg_engine.session_persistence import build_save_snapshot, load_session_from_snapshot


def test_object_private_data_round_trip_in_save():
    area = Area(bounds=GridBounds.square(4))
    from campaign_rpg_engine.area_edit import create_agent_from_args

    create_agent_from_args(
        area,
        'name "GM" pdesc "GM." desc "GM." personality "GM." at 0,0',
    )
    obj, _ = create_object_from_args(
        area,
        'name "Chest" pdesc "A chest." at 1,1',
    )
    obj.private_data = '{"hp": 10, "durability": 50}'

    session = Session(area=area)
    data = build_save_snapshot(session)
    loaded = load_session_from_snapshot(data)
    loaded_obj = loaded.area.get_object_by_id(obj.id)
    assert loaded_obj is not None
    assert loaded_obj.private_data == '{"hp": 10, "durability": 50}'


def test_agent_private_data_via_session_api():
    session = Session.from_default()
    agent = session.get_active_agent()
    result = session.set_entity_private_data(agent.id, "stamina=100")
    assert result.ok
    assert agent.private_data == "stamina=100"

    data = build_save_snapshot(session)
    loaded = load_session_from_snapshot(data)
    loaded_agent = loaded.get_agent(agent.id)
    assert loaded_agent is not None
    assert loaded_agent.private_data == "stamina=100"


def test_private_data_in_snapshot_not_in_llm_prompt():
    session = Session.from_default()
    agent = session.get_active_agent()
    agent.private_data = "secret_stats=99"
    prompt = session.build_prompt(agent.id)
    assert "secret_stats" not in prompt
    assert "private_data" not in prompt
