from app.db import as_workspace
from app.retrieve import retrieve
from tests.seed import ID, WS_A, embedder

QUESTION = "What did we promise Northwind before the renewal call?"


def test_renewal_question_brings_the_email_note_task_and_deal(db):
    with as_workspace(db, WS_A) as c:
        hits = retrieve(c, WS_A, QUESTION, embedder)
    ids = {h.record_id for h in hits}
    assert {ID["emailA"], ID["noteA"], ID["taskA"], ID["dealA"]} <= ids
    assert len(hits) <= 8


def test_full_text_catches_an_exact_amount_that_vectors_blur(db):
    with as_workspace(db, WS_A) as c:
        hits = retrieve(c, WS_A, "$48,000", embedder)
    assert hits[0].record_type in {"deal", "activity"}
