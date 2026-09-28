"""Embedding lifecycle: what a write does, and does not, cost."""

from app.core.tenancy import TenantCtx
from app.db.session import as_workspace
from app.modules.search.repository import SearchRepository
from app.modules.search.service import SearchService
from app.workers.tasks.embeddings import embed_pending
from tests.support.seed import ID, WS_A, embedder

DEAL = ID["dealA"]
CTX = TenantCtx(WS_A)


def test_change_that_does_not_alter_the_document_does_not_enqueue(db):
    with as_workspace(db, WS_A) as c:
        c.execute("update deals set updated_at = now() where id = %s", [DEAL])
        assert SearchService(SearchRepository(c), embedder).enqueue_if_changed(CTX, "deal", DEAL) is False


def test_content_change_enqueues_once_and_worker_reembeds(db):
    with as_workspace(db, WS_A) as c:
        before = c.execute("select content_hash from embeddings where record_id = %s", [DEAL]).fetchone()["content_hash"]
        c.execute("update deals set notes = 'Annual renewal. Price held at $48,000 for 12 months. Two extra seats included.' where id = %s", [DEAL])
        assert SearchService(SearchRepository(c), embedder).enqueue_if_changed(CTX, "deal", DEAL) is True
        assert embed_pending(c, CTX, embedder) == 1
        after = c.execute("select content_hash, content from embeddings where record_id = %s", [DEAL]).fetchone()
    assert bytes(after["content_hash"]) != bytes(before)
    assert "Two extra seats" in after["content"]


def test_deleting_a_record_removes_its_embedding_in_the_same_transaction(db):
    with as_workspace(db, WS_A) as c:
        c.execute("delete from leads where id = %s", [ID["leadA"]])
        left = c.execute("select 1 from embeddings where record_id = %s", [ID["leadA"]]).fetchall()
    assert left == []
