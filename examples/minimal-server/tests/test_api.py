"""HTTP smoke tests for minimal-server."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from minimal_server.app import create_app, reset_session_store


@pytest.fixture
def client() -> TestClient:
    reset_session_store()
    return TestClient(create_app())


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_state_has_bootstrapped_agent(client: TestClient) -> None:
    response = client.get("/api/state")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    assert any(a["name"] == "Explorer" for a in data["agents"])


def test_command_debug_endpoint(client: TestClient) -> None:
    response = client.post(
        "/api/command",
        json={"command": "objects"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert "Sign" in body["message"] or "obj_" in body["message"]
