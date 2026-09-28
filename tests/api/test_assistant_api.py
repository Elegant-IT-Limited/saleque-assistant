from tests.api.conftest import auth
from tests.support.seed import WS_A, WS_B

ASK = "/api/internal/assistant/ask"


def test_ask_returns_a_cited_answer_scoped_to_the_session_workspace(api):
    r = api.post(ASK, json={"question": "What did we promise Northwind before the renewal call?"}, headers=auth(WS_A))
    assert r.status_code == 200
    body = r.json()
    assert len(body["sentences"]) == 5 and len(body["citations"]) == 4
    assert all(s["sources"] for s in body["sentences"])
    assert (body["cache"], body["credits"]) == ("miss", 1)


def test_the_body_cannot_choose_the_workspace(api):
    r = api.post(ASK, json={"question": "Northwind price", "workspace_id": WS_B}, headers=auth(WS_A))
    assert r.status_code == 422


def test_a_forged_session_is_rejected(api):
    r = api.post(ASK, json={"question": "Northwind price"}, headers={"Authorization": f"Bearer {WS_B}.forged"})
    assert r.status_code == 401
