from app.db import as_workspace
from app.outbox import drain_outbox, enqueue_if_changed
from tests.seed import ID, WS_A, embedder

DEAL = ID["dealA"]


def test_change_that_does_not_alter_the_document_does_not_enqueue(db):
    with as_workspace(db, WS_A) as c:
        c.execute("update deals set updated_at = now() where id = %s", [DEAL])
        assert enqueue_if_changed(c, WS_A, "deal", DEAL) is False


def test_content_change_enqueues_once_and_worker_reembeds(db):
    with as_workspace(db, WS_A) as c:
        before = c.execute("select content_hash from embeddings where record_id = %s", [DEAL]).fetchone()["content_hash"]
        c.execute("update deals set notes = 'Annual renewal. Price held at $48,000 for 12 months. Two extra seats included.' where id = %s", [DEAL])
        assert enqueue_if_changed(c, WS_A, "deal", DEAL) is True
        assert drain_outbox(c, WS_A, embedder) == 1
        after = c.execute("select content_hash, content from embeddings where record_id = %s", [DEAL]).fetchone()
    assert bytes(after["content_hash"]) != bytes(before)
    assert "Two extra seats" in after["content"]


def test_deleting_a_record_removes_its_embedding_in_the_same_transaction(db):
    with as_workspace(db, WS_A) as c:
        c.execute("delete from leads where id = %s", [ID["leadA"]])
        left = c.execute("select 1 from embeddings where record_id = %s", [ID["leadA"]]).fetchall()
    assert left == []
