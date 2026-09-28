from app.core.tenancy import TenantCtx
from app.db.session import as_workspace
from app.modules.search.repository import SearchRepository
from app.modules.search.service import SearchService
from tests.support.seed import ID, WS_A, embedder

QUESTION = "What did we promise Northwind before the renewal call?"


def retrieve(db, question: str):
    with as_workspace(db, WS_A) as c:
        return SearchService(SearchRepository(c), embedder).retrieve(TenantCtx(WS_A), question)


def test_renewal_question_brings_the_email_note_task_and_deal(db):
    hits = retrieve(db, QUESTION)
    ids = {h.record_id for h in hits}
    assert {ID["emailA"], ID["noteA"], ID["taskA"], ID["dealA"]} <= ids
    assert len(hits) <= 8


def test_full_text_catches_an_exact_amount_that_vectors_blur(db):
    hits = retrieve(db, "$48,000")
    assert hits[0].record_type in {"deal", "activity"}
