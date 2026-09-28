from app.core.tenancy import TenantCtx
from app.db.session import as_workspace
from app.modules.ai.repository import AIRepository
from app.modules.ai.service import AIService
from app.modules.lead.repository import LeadRepository
from app.modules.lead.service import AUTO, LeadScoringService
from tests.support.fakes import FakeCompleter, fake_jev
from tests.support.seed import ID, WS_A


def score(db, key: str, seen: list | None = None):
    with as_workspace(db, WS_A) as c:
        ai = AIService(AIRepository(c), FakeCompleter(), fake_jev(seen))
        return LeadScoringService(LeadRepository(c), ai).score(TenantCtx(WS_A), ID[key])


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
