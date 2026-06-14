"""realm-studio API tests (V0.3.1–0.3.2d)."""

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.session_store import get_session_store, reset_session_store
from src.llm.schemas import AgentCompoundTurn
from src.llm.types import LLMResponse
from src.session import SessionResult


@pytest.fixture(autouse=True)
def _fresh_session_store():
    reset_session_store()
    yield
    reset_session_store()


@pytest.fixture
def client():
    return TestClient(create_app())


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_state_returns_snapshot_shape(client):
    response = client.get("/api/state")
    assert response.status_code == 200
    data = response.json()

    assert data["grid"] == {"min_x": 0, "max_x": 4, "min_y": 0, "max_y": 4}
    assert data["active_agent_id"] == "agent_01"
    assert data["session_turn"] == 0
    assert "passive_vision" in data
    assert "You are at (1, 1)" in data["passive_vision"]

    assert len(data["agents"]) == 1
    assert data["agents"][0]["name"] == "Explorer"
    assert data["agents"][0]["appearance"] == "tokens/explorer.svg"
    assert "personality" in data["agents"][0]
    assert "passive_description" in data["agents"][0]
    assert "description" in data["agents"][0]
    assert data["agents"][0]["move_speed"] is None

    object_ids = {o["id"] for o in data["objects"]}
    assert "obj_ball_01" in object_ids
    assert "obj_sign_01" in object_ids
    ball = next(o for o in data["objects"] if o["id"] == "obj_ball_01")
    assert ball["appearance"] == "tokens/ball.svg"
    assert "passive_description" in ball
    assert "description" in ball
    assert data["recent_events"] == []


def test_post_event_success(client):
    response = client.post(
        "/api/event",
        json={"text": "Thunder rumbles overhead."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "Thunder" in data["message"]
    assert data["snapshot"]["recent_events"] == [
        {"session_turn": 0, "text": "Thunder rumbles overhead."}
    ]
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
    assert state["recent_events"][-1]["text"] == "A door slams."


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
    crate = next(o for o in state["objects"] if o["name"] == "Token Crate")
    assert crate["appearance"] == "tokens/ball.svg"


def test_index_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "realm-studio" in response.text
    assert 'id="grid"' in response.text
    assert 'id="grid-viewport"' in response.text
    assert 'id="context-menu"' in response.text
    assert 'id="active-agent-select"' in response.text
    assert 'id="run-turn"' in response.text
    assert 'id="emit-event"' in response.text
    assert 'id="recent-events"' in response.text


def _fake_compound_response(_prompt):
    return LLMResponse(
        parsed=AgentCompoundTurn(
            reasoning="stay and speak",
            move_target=None,
            turn_action="speak",
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
    assert data["message"]
    assert isinstance(data["steps"], list)
    assert len(data["steps"]) >= 1
    assert data["snapshot"]["session_turn"] == 1
    assert "prompt" in data
    assert len(data["prompt"]) > 100


def test_get_prompt(client):
    response = client.get("/api/prompt")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert len(data["prompt"]) > 100
    assert data["length"] == len(data["prompt"])
    assert data["include_examples"] is False
    assert "You are at" in data["prompt"] or "Explorer" in data["prompt"]


def test_get_prompt_unknown_agent(client):
    response = client.get("/api/prompt", params={"agent_id": "nobody"})
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False


def test_post_turn_gate_blocked(client, monkeypatch):
    def blocked(_agent_id=None):
        return SessionResult(ok=False, message="Cannot run turn: consolidation pending.")

    session = get_session_store().session
    monkeypatch.setattr(session, "gate_agent_turn", blocked)

    response = client.post("/api/turn", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert "consolidation" in data["message"].lower()

    state = client.get("/api/state").json()
    assert state["session_turn"] == 0


def test_post_turn_missing_api_key(client, monkeypatch):
    def fail_llm(_prompt):
        raise RuntimeError("OPENROUTER_API_KEY not found.")

    monkeypatch.setattr("src.llm.client.get_compound_turn", fail_llm)

    response = client.post("/api/turn", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert "OPENROUTER_API_KEY" in data["message"]


def test_e2e_edit_then_turn(client, monkeypatch):
    """Smoke: area edit (no turn) then mocked LLM turn updates snapshot."""
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
    assert mid["session_turn"] == 0
    assert any(o["name"] == "E2E Crate" for o in mid["objects"])

    turn = client.post("/api/turn", json={})
    data = turn.json()
    assert data["ok"] is True
    assert data["snapshot"]["session_turn"] == 1
    assert "passive_vision" in data["snapshot"]
    assert isinstance(data["steps"], list)


def test_post_command_create_object(client):
    response = client.post(
        "/api/command",
        json={
            "line": 'create-object name "Test Crate" pdesc "A crate." desc "Wooden crate." at 2,2',
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True

    state = client.get("/api/state").json()
    names = {o["name"] for o in state["objects"]}
    assert "Test Crate" in names
    assert state["session_turn"] == 0


def test_post_command_invalid(client):
    response = client.post(
        "/api/command",
        json={"line": "not-a-real-command"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert data["message"]


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
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True

    state = client.get("/api/state").json()
    active = next(a for a in state["agents"] if a["name"] == "Goblin")
    assert state["active_agent_id"] == active["id"]
    assert state["session_turn"] == 0


def test_post_active_agent_unknown(client):
    response = client.post(
        "/api/active-agent",
        json={"name_or_id": "Nobody"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert data["message"]


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
    assert response.status_code == 200
    assert response.json()["ok"] is True

    state = client.get("/api/state").json()
    scout = next(a for a in state["agents"] if a["name"] == "Scout")
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
        json={"line": f'edit-agent {agent_id} move-speed 2'},
    )
    assert edit.json()["ok"] is True

    walker = next(
        a for a in client.get("/api/state").json()["agents"] if a["id"] == agent_id
    )
    assert walker["move_speed"] == 2
