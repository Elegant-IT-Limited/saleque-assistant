from app.db import as_workspace
from app.jev import AUTO, score_lead
from tests.fakes import fake_jev
from tests.seed import ID, WS_A


def score(db, key: str, seen: list | None = None):
    with as_workspace(db, WS_A) as c:
        return score_lead(c, WS_A, ID[key], fake_jev(seen))


def test_sends_typed_questions_to_system_one_and_routes_a_hot_lead_to_sales(db):
    seen: list = []
    route, res = score(db, "leadA", seen)
    body = seen[0]["body"]
    assert seen[0]["path"] == "/v1/systemone"
    assert {k: q["type"] for k, q in body["questions"].items()} == {"fit": "score", "intent": "choice", "has_budget": "noul"}
    assert body["state"]["ideal_customer"].startswith("B2B software teams")
    assert (route.owner, route.priority) == ("sales", "high")
    assert res.choices["intent"].confidence >= AUTO


def test_low_confidence_goes_to_a_person_not_to_a_guess(db):
    route, res = score(db, "leadVague")
    assert res.choices["intent"].confidence < AUTO
    assert (route.owner, route.priority) == ("review", "normal")


def test_confident_noise_is_archived(db):
    route, _ = score(db, "leadSpam")
    assert route.owner == "archived"


def test_every_decision_is_stored_and_metered_inside_the_workspace(db):
    with as_workspace(db, WS_A) as c:
        rows = c.execute("select owner from lead_scores order by owner").fetchall()
        led = c.execute("select count(*) as n from ai_ledger where feature = 'lead.score' and provider = 'typesafe'").fetchone()
    assert [r["owner"] for r in rows] == ["archived", "review", "sales"]
    assert led["n"] == 3
