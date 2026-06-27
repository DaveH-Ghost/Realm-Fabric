"""realm-studio API tests (V0.3.1–0.4.0c2)."""

from pathlib import Path

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
            action="none",
            say="Hello from the test.",
        ),
        raw_response="{}",
        prompt_tokens=512,
        completion_tokens=42,
        total_tokens=554,
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
    assert data["prompt_tokens"] == 512
    assert data["completion_tokens"] == 42
    assert data["total_tokens"] == 554
    assert isinstance(data["prompt_tokens_estimate"], int)
    assert data["prompt_tokens_estimate"] > 0


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


def test_post_command_create_object_blocks_movement(client):
    response = client.post(
        "/api/command",
        json={
            "line": (
                'create-object name "Passable" pdesc "Open." at 1,3 blocks-movement false'
            ),
        },
    )
    assert response.json()["ok"] is True

    state = client.get("/api/state").json()
    obj = next(o for o in _room(state)["objects"] if o["name"] == "Passable")
    assert obj["blocks_movement"] is False


def test_post_command_edit_object_movement_exceptions(client):
    create = client.post(
        "/api/command",
        json={
            "line": 'create-object name "Gate" pdesc "A gate." at 0,4',
        },
    )
    assert create.json()["ok"] is True
    state_after_create = client.get("/api/state").json()
    obj_id = next(
        o["id"] for o in _room(state_after_create)["objects"] if o["name"] == "Gate"
    )

    edit = client.post(
        "/api/command",
        json={
            "line": f'edit-object {obj_id} movement-exception agent_01',
        },
    )
    assert edit.json()["ok"] is True

    state = client.get("/api/state").json()
    obj = next(o for o in _room(state)["objects"] if o["id"] == obj_id)
    assert obj["blocks_movement"] is True
    assert obj["movement_exceptions"] == ["agent_01"]


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


@pytest.fixture(autouse=True)
def _clear_custom_memory_modules():
    import shutil

    from backend.memory_module_upload import CUSTOM_MODULES_DIR
    from src.memory_modules import registry

    registry._CUSTOM_REGISTRY.clear()
    registry._CUSTOM_METADATA.clear()
    if CUSTOM_MODULES_DIR.is_dir():
        shutil.rmtree(CUSTOM_MODULES_DIR)
    yield
    registry._CUSTOM_REGISTRY.clear()
    registry._CUSTOM_METADATA.clear()
    if CUSTOM_MODULES_DIR.is_dir():
        shutil.rmtree(CUSTOM_MODULES_DIR)


def test_get_llm_settings_never_returns_api_key(client):
    response = client.get("/api/settings/llm")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "api_key" not in data
    assert "key_configured" in data
    assert "model" in data


def test_put_llm_settings_in_memory(client, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    response = client.put(
        "/api/settings/llm",
        json={"api_key": "test-key", "model": "test/model"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["key_configured"] is True
    assert data["model"] == "test/model"
    get_resp = client.get("/api/settings/llm")
    get_data = get_resp.json()
    assert get_data["key_configured"] is True
    assert "api_key" not in get_data


def _example_custom_module_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "custom_memory"
        / "rolling_summary_custom.py"
    )


def test_upload_memory_module_lists_in_catalog(client):
    example = _example_custom_module_path()
    source = example.read_text(encoding="utf-8")
    response = client.post(
        "/api/memory-modules/upload",
        files={"file": ("rolling_summary_custom.py", source, "text/x-python")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["module_id"] == "rolling_summary_custom"

    catalog = client.get("/api/memory-modules").json()
    ids = {mod["id"] for mod in catalog["modules"]}
    assert "rolling_summary_custom" in ids
    assert catalog["custom_modules"]
    assert catalog["custom_modules"][0]["id"] == "rolling_summary_custom"


def test_cached_modules_reload_from_disk_after_registry_clear(client):
    example = _example_custom_module_path()
    source = example.read_text(encoding="utf-8")
    upload = client.post(
        "/api/memory-modules/upload",
        files={"file": ("rolling_summary_custom.py", source, "text/x-python")},
    )
    assert upload.status_code == 200

    from backend.memory_module_upload import CUSTOM_MODULES_DIR, load_cached_custom_modules
    from src.memory_modules import registry

    assert list(CUSTOM_MODULES_DIR.glob("*.py"))

    registry._CUSTOM_REGISTRY.clear()
    registry._CUSTOM_METADATA.clear()

    loaded = load_cached_custom_modules()
    assert "rolling_summary_custom" in loaded

    catalog = client.get("/api/memory-modules").json()
    ids = {mod["id"] for mod in catalog["modules"]}
    assert "rolling_summary_custom" in ids


def test_session_import_fails_without_custom_module(client):
    from src.memory_modules.registry import register_memory_module_from_path

    example = _example_custom_module_path()
    register_memory_module_from_path(example)
    client.post(
        "/api/command",
        json={
            "line": (
                'create-agent name "Archivist" personality "x" '
                "memory rolling_summary_custom at 2,2"
            ),
        },
    )
    snapshot = client.get("/api/session/export").json()

    from src.memory_modules import registry

    registry._CUSTOM_REGISTRY.clear()
    registry._CUSTOM_METADATA.clear()

    response = client.post("/api/session/import", json=snapshot)
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "rolling_summary_custom" in detail
    assert "not found" in detail.lower()


_LOREBOOK_JSON = """{
  "entries": {
    "0": {
      "uid": 0,
      "key": ["midway"],
      "keysecondary": [],
      "comment": "Midway",
      "content": "The Midway is a megastructure.",
      "constant": true,
      "disable": false,
      "selective": false,
      "selectiveLogic": 0,
      "order": 0
    }
  }
}"""


def test_create_lorebook_api(client):
    response = client.post("/api/lorebooks", json={"name": "Scratch pad"})
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["lorebook_id"] == "scratch-pad"
    assert data["lorebook"]["entries"] == []

    detail = client.get("/api/lorebooks/scratch-pad").json()
    assert detail["ok"] is True
    assert detail["lorebook"]["name"] == "Scratch pad"


def test_load_demo_lorebook_api(client):
    response = client.post("/api/lorebooks/load-demo")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["lorebook_id"] == "realm-fabric-demo"
    assert len(data["lorebook"]["entries"]) == 3

    listing = client.get("/api/lorebooks").json()
    ids = {book["id"] for book in listing["lorebooks"]}
    assert "realm-fabric-demo" in ids


def test_upload_lorebook_and_list(client):
    response = client.post(
        "/api/lorebooks/upload",
        files={"file": ("test.lorebook.json", _LOREBOOK_JSON, "application/json")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    book_id = data["lorebook_id"]

    listing = client.get("/api/lorebooks").json()
    ids = {book["id"] for book in listing["lorebooks"]}
    assert book_id in ids

    detail = client.get(f"/api/lorebooks/{book_id}").json()
    assert detail["ok"] is True
    assert detail["lorebook"]["entries"][0]["content"].startswith("The Midway")


def test_put_lorebook_updates_entry(client):
    client.post(
        "/api/lorebooks/upload",
        files={"file": ("edit-me.lorebook.json", _LOREBOOK_JSON, "application/json")},
    )
    book_id = client.get("/api/lorebooks").json()["lorebooks"][0]["id"]
    book = client.get(f"/api/lorebooks/{book_id}").json()["lorebook"]
    book["entries"][0]["content"] = "Updated lore text."
    book["entries"][0]["enabled"] = False
    response = client.put(f"/api/lorebooks/{book_id}", json=book)
    assert response.status_code == 200
    saved = response.json()["lorebook"]["entries"][0]
    assert saved["content"] == "Updated lore text."
    assert saved["enabled"] is False


def test_put_lorebook_add_and_remove_entries(client):
    client.post(
        "/api/lorebooks/upload",
        files={"file": ("mutable.lorebook.json", _LOREBOOK_JSON, "application/json")},
    )
    book_id = client.get("/api/lorebooks").json()["lorebooks"][0]["id"]
    book = client.get(f"/api/lorebooks/{book_id}").json()["lorebook"]
    assert len(book["entries"]) == 1

    book["entries"].append(
        {
            "uid": 99,
            "enabled": True,
            "constant": False,
            "keys": ["session-only"],
            "keys_secondary": [],
            "selective": False,
            "selective_logic": 0,
            "content": "Custom session lore.",
            "comment": "Session extra",
            "order": 1,
            "ignore_budget": False,
        }
    )
    response = client.put(f"/api/lorebooks/{book_id}", json=book)
    assert response.status_code == 200
    saved = response.json()["lorebook"]
    assert len(saved["entries"]) == 2
    assert saved["entries"][1]["content"] == "Custom session lore."
    downloaded = client.get(f"/api/lorebooks/{book_id}/download").json()
    new_entry = downloaded["entries"]["99"]
    assert new_entry["probability"] == 100
    assert new_entry["depth"] == 4

    book = saved
    book["entries"] = [book["entries"][1]]
    response = client.put(f"/api/lorebooks/{book_id}", json=book)
    assert response.status_code == 200
    saved = response.json()["lorebook"]
    assert len(saved["entries"]) == 1
    assert saved["entries"][0]["comment"] == "Session extra"


_LOREBOOK_WITH_DEFERRED = """{
  "entries": {
    "0": {
      "uid": 0,
      "key": ["midway"],
      "content": "The Midway is a megastructure.",
      "constant": true,
      "disable": false,
      "selective": false,
      "selectiveLogic": 0,
      "order": 0,
      "probability": 100,
      "position": 4
    }
  }
}"""


def test_download_lorebook_st_json(client):
    client.post(
        "/api/lorebooks/upload",
        files={
            "file": ("world.lorebook.json", _LOREBOOK_WITH_DEFERRED, "application/json"),
        },
    )
    book_id = client.get("/api/lorebooks").json()["lorebooks"][0]["id"]
    book = client.get(f"/api/lorebooks/{book_id}").json()["lorebook"]
    book["entries"][0]["content"] = "Edited Midway text."
    book["entries"][0]["enabled"] = False
    client.put(f"/api/lorebooks/{book_id}", json=book)

    response = client.get(f"/api/lorebooks/{book_id}/download")
    assert response.status_code == 200
    assert "attachment" in response.headers.get("content-disposition", "").lower()
    payload = response.json()
    entry = payload["entries"]["0"]
    assert entry["content"] == "Edited Midway text."
    assert entry["disable"] is True
    assert entry["constant"] is True
    assert entry["probability"] == 100
    assert entry["position"] == 4
    assert "enabled" not in entry


def test_lorebook_scan_config_api(client):
    listing = client.get("/api/lorebooks/scan-config").json()
    assert listing["ok"] is True
    source_ids = {row["id"] for row in listing["sources"]}
    assert "passive_vision" in source_ids
    assert "memory" in source_ids

    updated = client.put(
        "/api/lorebooks/scan-config",
        json={"memory": False, "passive_vision": True},
    ).json()
    assert updated["ok"] is True
    assert updated["config"]["memory"] is False
    by_id = {row["id"]: row for row in updated["sources"]}
    assert by_id["memory"]["enabled"] is False
    assert by_id["passive_vision"]["enabled"] is True


def test_prompt_preview_includes_lorebook_slot(client):
    client.post(
        "/api/lorebooks/upload",
        files={"file": ("world.lorebook.json", _LOREBOOK_JSON, "application/json")},
    )
    book_id = client.get("/api/lorebooks").json()["lorebooks"][0]["id"]
    base = client.get("/api/prompt-blocks").json()["blocks"]
    blocks = list(base)
    blocks.insert(
        1,
        {
            "type": "slot",
            "name": "lorebook",
            "options": {"lorebook_id": book_id},
        },
    )
    preview = client.post("/api/prompt-blocks/preview", json={"blocks": blocks}).json()
    lore_block = next(b for b in preview["blocks"] if b.get("name") == "lorebook")
    assert "World info:" in lore_block.get("preview", "")


def _create_player_agent(client, name="Tester"):
    response = client.post(
        "/api/command",
        json={
            "line": (
                f'create-agent name "{name}" personality "Manual tester." '
                f"player true at 0,0"
            ),
        },
    )
    assert response.json()["ok"] is True
    state = client.get("/api/state").json()
    return next(agent for agent in state["agents"] if agent["name"] == name)


def test_create_player_agent_in_snapshot(client):
    agent = _create_player_agent(client)
    assert agent["is_player"] is True
    assert agent["id"].startswith("agent_")


def test_post_manual_turn_moves_player(client):
    agent = _create_player_agent(client)
    client.post("/api/active-agent", json={"name_or_id": agent["id"]})

    response = client.post(
        "/api/turn/manual",
        json={
            "compound_turn": {
                "reasoning": "Walk east.",
                "move": "2,0",
                "action": "none",
            },
        },
    )
    data = response.json()
    assert data["ok"] is True
    assert data["manual_turn"] is True
    assert data["snapshot"]["session_turn"] == 1
    updated = next(item for item in data["snapshot"]["agents"] if item["id"] == agent["id"])
    assert updated["position"] == [2, 0]


def test_post_turn_rejects_player_agent(client):
    agent = _create_player_agent(client)
    client.post("/api/active-agent", json={"name_or_id": agent["id"]})

    response = client.post("/api/turn", json={})
    data = response.json()
    assert data["ok"] is False
    assert "player" in data["message"].lower()


def test_post_manual_turn_rejects_llm_agent(client, monkeypatch):
    monkeypatch.setattr(
        "src.llm.client.get_compound_turn",
        _fake_compound_response,
    )
    response = client.post(
        "/api/turn/manual",
        json={
            "compound_turn": {
                "reasoning": "Nope.",
                "action": "none",
            },
        },
    )
    data = response.json()
    assert data["ok"] is False
    assert "player" in data["message"].lower()
