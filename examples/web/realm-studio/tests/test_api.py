"""realm-studio API tests (V0.3.1–0.4.0c2)."""

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.session_store import get_session_store, reset_session_store
from src.llm.schemas import AgentCompoundTurn
from src.llm.types import LLMResponse
from src.session import SessionResult

ROOM = "room"
HALL = "hall"


@pytest.fixture(autouse=True)
def _fresh_session_store():
    reset_session_store()
    yield
    reset_session_store()


@pytest.fixture
def client():
    return TestClient(create_app())


def _room(state: dict) -> dict:
    return state["areas"][ROOM]


def _active_block(state: dict) -> dict:
    return state["areas"][state["active_area_id"]]


def test_get_state_includes_vision_units(client):
    response = client.get("/api/state")
    data = response.json()
    assert data.get("vision_units") == ""
    assert data.get("vision_units_per_tile") is None


def test_put_vision_units(client):
    response = client.put(
        "/api/vision-units",
        json={"units": "ft", "units_per_tile": 5},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["vision_units"] == "ft"
    assert data["vision_units_per_tile"] == 5
    assert data["snapshot"]["vision_units"] == "ft"


def test_put_vision_units_rejects_invalid_units(client):
    response = client.put(
        "/api/vision-units",
        json={"units": "ft5", "units_per_tile": 5},
    )
    assert response.json()["ok"] is False


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_interact_template_vars(client):
    response = client.get("/api/interact-template-vars")
    assert response.status_code == 200
    data = response.json()
    names = {item["name"] for item in data["vars"]}
    assert "actor" in names
    assert "object_start" in names
    assert "actor_end_area" in names
    assert "{actor}" in data["vars"][0]["placeholder"]


def test_state_returns_multi_area_snapshot(client):
    response = client.get("/api/state")
    assert response.status_code == 200
    data = response.json()

    assert data["active_area_id"] == ROOM
    assert ROOM in data["areas"]
    assert HALL in data["areas"]
    assert _room(data)["grid"] == {"min_x": 0, "max_x": 4, "min_y": 0, "max_y": 4}
    assert data["active_agent_id"] == "agent_01"
    assert data["session_turn"] == 0
    assert "passive_vision" in data
    assert "You are at (1, 1)" in data["passive_vision"]

    assert len(data["agents"]) == 1
    assert data["agents"][0]["name"] == "Explorer"
    assert data["agents"][0]["area_id"] == ROOM
    assert data["agents"][0]["appearance"] == "tokens/explorer.svg"
    assert "personality" in data["agents"][0]
    assert data["agents"][0]["move_speed"] is None

    room_objects = _room(data)["objects"]
    object_ids = {o["id"] for o in room_objects}
    assert "obj_ball_01" in object_ids
    assert "obj_sign_01" in object_ids
    ball = next(o for o in room_objects if o["id"] == "obj_ball_01")
    assert "kick" in ball["actions"]
    assert ball["actions_detail"]["kick"]["range"] == 1
    assert ball["actions_detail"]["kick"]["effects"][0]["name"] == "random_move_self"
    assert isinstance(_room(data)["objects"], list)
    assert isinstance(_room(data)["recent_events"], list)
    assert isinstance(_active_block(data)["objects"], list)


def test_hall_area_has_objects_array(client):
    data = client.get("/api/state").json()
    assert isinstance(data["areas"][HALL]["objects"], list)
    assert data["areas"][HALL]["objects"] == []


def test_post_event_success(client):
    response = client.post(
        "/api/event",
        json={"text": "Thunder rumbles overhead."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "Thunder" in data["message"]
    events = data["snapshot"]["areas"][ROOM]["recent_events"]
    assert events == [{"session_turn": 0, "text": "Thunder rumbles overhead."}]
    assert data["snapshot"]["session_turn"] == 0
    assert "Thunder rumbles overhead." not in data["snapshot"]["passive_vision"]


def test_post_event_empty_rejected(client):
    response = client.post("/api/event", json={"text": ""})
    assert response.status_code == 422


def test_post_event_whitespace_fails(client):
    response = client.post("/api/event", json={"text": "   "})
    assert response.status_code == 200
    assert response.json()["ok"] is False


def test_post_event_via_state(client):
    client.post("/api/event", json={"text": "A door slams."})
    state = client.get("/api/state").json()
    assert _room(state)["recent_events"][-1]["text"] == "A door slams."


def test_post_active_area_switch(client):
    response = client.post("/api/active-area", json={"area_id": HALL})
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["snapshot"]["active_area_id"] == HALL
    assert isinstance(data["snapshot"]["areas"][HALL]["objects"], list)

    state = client.get("/api/state").json()
    assert state["active_area_id"] == HALL


def test_post_active_area_unknown(client):
    response = client.post("/api/active-area", json={"area_id": "attic"})
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False


def test_create_object_scoped_to_active_area(client):
    client.post("/api/active-area", json={"area_id": HALL})
    create = client.post(
        "/api/command",
        json={'line': 'create-object name "Bench" pdesc "A bench." at 2,2'},
    )
    assert create.json()["ok"] is True

    state = client.get("/api/state").json()
    hall_names = {o["name"] for o in state["areas"][HALL]["objects"]}
    room_names = {o["name"] for o in state["areas"][ROOM]["objects"]}
    assert "Bench" in hall_names
    assert "Bench" not in room_names


def test_static_token_assets(client):
    for path in (
        "/static/tokens/explorer.svg",
        "/static/tokens/ball.svg",
        "/static/tokens/sign.svg",
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert "svg" in response.headers.get("content-type", "").lower()


def test_post_command_appearance(client):
    response = client.post(
        "/api/command",
        json={
            "line": (
                'create-object name "Token Crate" appearance "tokens/ball.svg" at 3,3'
            ),
        },
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True

    state = client.get("/api/state").json()
    crate = next(o for o in _room(state)["objects"] if o["name"] == "Token Crate")
    assert crate["appearance"] == "tokens/ball.svg"


def test_index_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "realm-studio" in response.text
    assert 'id="grid"' in response.text
    assert 'id="active-area-select"' in response.text
    assert 'id="create-area"' in response.text
    assert 'id="edit-area"' in response.text
    assert 'id="delete-area"' in response.text
    assert 'id="last-prompt"' in response.text
    assert 'id="last-response"' in response.text


def _fake_compound_response(_prompt):
    return LLMResponse(
        parsed=AgentCompoundTurn(
            reasoning="stay and speak",
            move_target=None,
            turn_action="none",
            content="Hello from the test.",
        ),
        raw_response="{}",
    )


def test_post_turn_success(client, monkeypatch):
    monkeypatch.setattr(
        "src.llm.client.get_compound_turn",
        _fake_compound_response,
    )

    response = client.post("/api/turn", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["snapshot"]["session_turn"] == 1
    assert "areas" in data["snapshot"]
    assert "prompt" in data
    assert data["llm_response"] == "{}"


def test_get_prompt(client):
    response = client.get("/api/prompt")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert len(data["prompt"]) > 100
    assert isinstance(data["prompt_tokens"], int)
    assert data["prompt_tokens"] > 0


def test_get_prompt_unknown_agent(client):
    response = client.get("/api/prompt", params={"agent_id": "nobody"})
    assert response.status_code == 200
    assert response.json()["ok"] is False


def test_get_prompt_blocks_default(client):
    response = client.get("/api/prompt-blocks")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["uses_default"] is True
    assert len(data["blocks"]) > 5
    assert data["blocks"][0]["type"] == "slot"


def test_put_prompt_blocks_reorder(client):
    base = client.get("/api/prompt-blocks").json()
    blocks = list(base["blocks"])
    blocks.insert(0, {"type": "text", "content": "API START\n"})
    put = client.put("/api/prompt-blocks", json={"blocks": blocks})
    assert put.status_code == 200
    assert put.json()["ok"] is True
    assert put.json()["uses_default"] is False

    prompt = client.get("/api/prompt").json()["prompt"]
    assert prompt.startswith("API START")


def test_put_prompt_blocks_invalid(client):
    response = client.put(
        "/api/prompt-blocks",
        json={"blocks": [{"type": "slot", "name": "bad_slot"}]},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is False


def test_reset_prompt_blocks(client):
    blocks = client.get("/api/prompt-blocks").json()["blocks"]
    blocks[0] = {"type": "text", "content": "TEMP\n"}
    client.put("/api/prompt-blocks", json={"blocks": blocks})
    reset = client.post("/api/prompt-blocks/reset")
    assert reset.status_code == 200
    assert reset.json()["uses_default"] is True


def test_get_prompt_slots(client):
    response = client.get("/api/prompt-slots")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    names = {item["name"] for item in data["slots"]}
    assert "passive_vision" in names
    assert "memory" in names
    assert "compound_rules" in data["editable_sections"]


def test_get_prompt_block_catalog(client):
    response = client.get("/api/prompt-block-catalog")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    types = {entry["type"] for entry in data["block_types"]}
    assert types == {"slot", "text", "section"}
    assert "character" in data["slot_settings"]


def test_get_memory_modules(client):
    response = client.get("/api/memory-modules")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["default_id"] == "recent_turns"
    ids = {mod["id"] for mod in data["modules"]}
    assert ids == {"recent_turns", "salient_turns", "rolling_summary"}
    salient = next(m for m in data["modules"] if m["id"] == "salient_turns")
    assert salient["options"][0]["flag"] == "memory-budget"
    recent = next(m for m in data["modules"] if m["id"] == "recent_turns")
    assert recent["options"][0]["flag"] == "memory-window"
    rolling = next(m for m in data["modules"] if m["id"] == "rolling_summary")
    assert len(rolling["options"]) == 3


def test_post_command_create_agent_with_recent_turns_memory_window(client):
    response = client.post(
        "/api/command",
        json={
            "line": (
                'create-agent name "Watcher" pdesc "A watcher." desc "Alert watcher." '
                'personality "You watch." memory recent_turns memory-window 5 at 2,2'
            ),
        },
    )
    assert response.json()["ok"] is True
    agent = next(
        a for a in client.get("/api/state").json()["agents"] if a["name"] == "Watcher"
    )
    assert agent["memory_module"] == "recent_turns"


def test_post_command_create_agent_with_salient_memory(client):
    response = client.post(
        "/api/command",
        json={
            "line": (
                'create-agent name "Scribe" pdesc "A scribe." desc "Quiet scribe." '
                'personality "You are a scribe." memory salient_turns memory-budget 1200 at 1,1'
            ),
        },
    )
    assert response.json()["ok"] is True
    agent = next(
        a for a in client.get("/api/state").json()["agents"] if a["name"] == "Scribe"
    )
    assert agent["memory_module"] == "salient_turns"


def test_preview_prompt_blocks_character_options(client):
    base = client.get("/api/prompt-blocks").json()["blocks"]
    blocks = list(base)
    blocks[0] = {
        "type": "slot",
        "name": "character",
        "options": {
            "include_name": True,
            "include_personality": False,
            "include_description": False,
        },
    }
    response = client.post("/api/prompt-blocks/preview", json={"blocks": blocks})
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    preview = data["blocks"][0]["preview"]
    assert preview.startswith("You are ")
    assert "Your personality:" not in preview


def test_preview_prompt_blocks_passive_vision_relative_bearing(client):
    client.put("/api/vision-units", json={"units": "ft", "units_per_tile": 5})
    base = client.get("/api/prompt-blocks").json()["blocks"]
    blocks = list(base)
    passive_index = next(
        i for i, block in enumerate(blocks) if block.get("name") == "passive_vision"
    )
    blocks[passive_index] = {
        "type": "slot",
        "name": "passive_vision",
        "options": {"include_relative_bearing": True},
    }
    response = client.post("/api/prompt-blocks/preview", json={"blocks": blocks})
    preview = response.json()["blocks"][passive_index]["preview"]
    assert "South of you, 15 ft away" in preview


def test_preview_prompt_blocks_passive_vision_options(client):
    base = client.get("/api/prompt-blocks").json()["blocks"]
    blocks = list(base)
    passive_index = next(
        i for i, block in enumerate(blocks) if block.get("name") == "passive_vision"
    )
    blocks[passive_index] = {
        "type": "slot",
        "name": "passive_vision",
        "options": {
            "include_you_are_at": False,
            "include_entity_coordinates": False,
        },
    }
    response = client.post("/api/prompt-blocks/preview", json={"blocks": blocks})
    assert response.status_code == 200
    preview = response.json()["blocks"][passive_index]["preview"]
    assert "You are at" not in preview
    assert "Ceramic Ball (obj_ball_01), (2, 2)" not in preview
    assert "Ceramic Ball (obj_ball_01)" in preview


def test_get_prompt_blocks_includes_slot_preview(client):
    response = client.get("/api/prompt-blocks")
    data = response.json()
    character = next(block for block in data["blocks"] if block.get("name") == "character")
    assert "preview" in character
    assert character["preview"]


def test_post_turn_gate_blocked(client, monkeypatch):
    def blocked(_agent_id=None):
        return SessionResult(ok=False, message="Cannot run turn: consolidation pending.")

    session = get_session_store().session
    monkeypatch.setattr(session, "gate_agent_turn", blocked)

    response = client.post("/api/turn", json={})
    assert response.json()["ok"] is False


def test_post_turn_missing_api_key(client, monkeypatch):
    def fail_llm(_prompt):
        raise RuntimeError("OPENROUTER_API_KEY not found.")

    monkeypatch.setattr("src.llm.client.get_compound_turn", fail_llm)
    response = client.post("/api/turn", json={})
    assert response.json()["ok"] is False


def test_e2e_edit_then_turn(client, monkeypatch):
    monkeypatch.setattr(
        "src.llm.client.get_compound_turn",
        _fake_compound_response,
    )

    create = client.post(
        "/api/command",
        json={
            "line": 'create-object name "E2E Crate" pdesc "A crate." desc "Test crate." at 2,2',
        },
    )
    assert create.json()["ok"] is True

    mid = client.get("/api/state").json()
    assert any(o["name"] == "E2E Crate" for o in _room(mid)["objects"])

    turn = client.post("/api/turn", json={})
    data = turn.json()
    assert data["ok"] is True
    assert data["snapshot"]["session_turn"] == 1


def test_post_command_create_object(client):
    response = client.post(
        "/api/command",
        json={
            "line": 'create-object name "Test Crate" pdesc "A crate." desc "Wooden crate." at 2,2',
        },
    )
    assert response.json()["ok"] is True

    state = client.get("/api/state").json()
    names = {o["name"] for o in _room(state)["objects"]}
    assert "Test Crate" in names


def test_post_command_invalid(client):
    response = client.post(
        "/api/command",
        json={"line": "not-a-real-command"},
    )
    assert response.json()["ok"] is False


def test_post_active_agent(client):
    create = client.post(
        "/api/command",
        json={
            "line": (
                'create-agent name "Goblin" pdesc "A goblin." desc "Small goblin." '
                'personality "You are a goblin." at 0,0'
            ),
        },
    )
    assert create.json()["ok"] is True

    response = client.post(
        "/api/active-agent",
        json={"name_or_id": "Goblin"},
    )
    assert response.json()["ok"] is True

    state = client.get("/api/state").json()
    active = next(a for a in state["agents"] if a["name"] == "Goblin")
    assert state["active_agent_id"] == active["id"]


def test_post_active_agent_unknown(client):
    response = client.post(
        "/api/active-agent",
        json={"name_or_id": "Nobody"},
    )
    assert response.json()["ok"] is False


def test_post_command_create_agent_with_move_speed(client):
    response = client.post(
        "/api/command",
        json={
            "line": (
                'create-agent name "Scout" pdesc "A scout." desc "Fast scout." '
                'personality "You are a scout." move-speed 3 at 0,0'
            ),
        },
    )
    assert response.json()["ok"] is True

    scout = next(a for a in client.get("/api/state").json()["agents"] if a["name"] == "Scout")
    assert scout["move_speed"] == 3


def test_post_command_edit_agent_move_speed(client):
    create = client.post(
        "/api/command",
        json={
            "line": (
                'create-agent name "Walker" pdesc "A walker." desc "Slow walker." '
                'personality "You walk." at 0,0'
            ),
        },
    )
    assert create.json()["ok"] is True
    agent_id = next(
        a["id"] for a in client.get("/api/state").json()["agents"] if a["name"] == "Walker"
    )

    edit = client.post(
        "/api/command",
        json={"line": f"edit-agent {agent_id} move-speed 2"},
    )
    assert edit.json()["ok"] is True

    walker = next(
        a for a in client.get("/api/state").json()["agents"] if a["id"] == agent_id
    )
    assert walker["move_speed"] == 2


def test_post_command_create_area(client):
    response = client.post(
        "/api/command",
        json={
            "line": 'create-area id attic desc "A dusty attic." width 6 height 4',
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "snapshot" in data
    assert "attic" in data["snapshot"]["areas"]
    assert data["snapshot"]["active_area_id"] == "attic"


def test_post_command_edit_area(client):
    client.post(
        "/api/command",
        json={"line": 'create-area id cellar desc "Old cellar." width 5 height 5'},
    )
    response = client.post(
        "/api/command",
        json={"line": 'edit-area cellar desc "Damp cellar." width 7 height 7'},
    )
    data = response.json()
    assert data["ok"] is True
    block = data["snapshot"]["areas"]["cellar"]
    assert block["area_description"] == "Damp cellar."
    assert block["grid"]["max_x"] - block["grid"]["min_x"] + 1 == 7


def test_post_command_delete_area(client):
    client.post(
        "/api/command",
        json={"line": 'create-area id closet desc "Empty closet."'},
    )
    response = client.post(
        "/api/command",
        json={"line": "delete-area closet"},
    )
    data = response.json()
    assert data["ok"] is True
    assert "closet" not in data["snapshot"]["areas"]


def test_post_command_delete_area_with_agents_rejected(client):
    response = client.post(
        "/api/command",
        json={"line": f"delete-area {ROOM}"},
    )
    assert response.json()["ok"] is False


def test_post_create_area_route(client):
    response = client.post(
        "/api/create-area",
        json={
            "area_id": "attic",
            "description": "A dusty attic.",
            "width": 6,
            "height": 4,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "attic" in data["snapshot"]["areas"]
    assert data["snapshot"]["active_area_id"] == "attic"


def test_post_edit_area_route(client):
    client.post(
        "/api/create-area",
        json={"area_id": "cellar", "description": "Old cellar.", "width": 5, "height": 5},
    )
    response = client.post(
        "/api/edit-area",
        json={
            "area_id": "cellar",
            "description": "Damp cellar.",
            "width": 7,
            "height": 7,
        },
    )
    data = response.json()
    assert data["ok"] is True
    block = data["snapshot"]["areas"]["cellar"]
    assert block["area_description"] == "Damp cellar."


def test_post_delete_area_route(client):
    client.post(
        "/api/create-area",
        json={"area_id": "closet", "description": "Empty closet."},
    )
    response = client.post("/api/delete-area", json={"area_id": "closet"})
    data = response.json()
    assert data["ok"] is True
    assert "closet" not in data["snapshot"]["areas"]
