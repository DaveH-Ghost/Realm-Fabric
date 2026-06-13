"""realm-studio API tests (V0.3.1a)."""

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.session_store import reset_session_store


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

    object_ids = {o["id"] for o in data["objects"]}
    assert "obj_ball_01" in object_ids
    assert "obj_sign_01" in object_ids


def test_index_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "realm-studio" in response.text
    assert 'id="grid"' in response.text
