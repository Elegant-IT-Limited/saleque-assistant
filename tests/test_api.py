import pytest
from fastapi.testclient import TestClient

from app.api import Services, create_app, sign
from tests.fakes import FakeCompleter, fake_jev
from tests.seed import ID, WS_A, WS_B, embedder

SECRET = b"test-secret"


@pytest.fixture(scope="module")
def api(db):
    return TestClient(create_app(Services(db, embedder, FakeCompleter(), fake_jev(), SECRET)))


def auth(ws: str) -> dict:
    return {"Authorization": "Bearer " + sign(ws, SECRET)}


def test_ask_returns_a_cited_answer_scoped_to_the_session_workspace(api):
    r = api.post("/v1/assistant/ask", json={"question": "What did we promise Northwind before the renewal call?"}, headers=auth(WS_A))
    assert r.status_code == 200
    body = r.json()
    assert len(body["sentences"]) == 5 and len(body["citations"]) == 4
    assert all(s["sources"] for s in body["sentences"])
    assert (body["cache"], body["credits"]) == ("miss", 1)


def test_the_body_cannot_choose_the_workspace(api):
    r = api.post("/v1/assistant/ask", json={"question": "Northwind price", "workspace_id": WS_B}, headers=auth(WS_A))
    assert r.status_code == 422


def test_a_forged_session_is_rejected(api):
    r = api.post("/v1/assistant/ask", json={"question": "Northwind price"}, headers={"Authorization": f"Bearer {WS_B}.forged"})
    assert r.status_code == 401


def test_scoring_another_workspaces_lead_is_a_404_not_a_leak(api):
    assert api.post(f"/v1/leads/{ID['leadA']}/score", headers=auth(WS_A)).json()["owner"] == "sales"
    assert api.post(f"/v1/leads/{ID['leadB']}/score", headers=auth(WS_A)).status_code == 404
