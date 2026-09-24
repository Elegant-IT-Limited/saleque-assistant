import psycopg
import pytest

from app.db import as_workspace
from app.retrieve import retrieve
from tests.seed import B_IDS, WS_A, WS_B, embedder

ADVERSARIAL = [
    "Northwind price freeze", "Lars Petersen", "Northwind expansion 120 seats", "manufacturing group Rotterdam",
    "what did we promise Northwind", "$48,000 deal", "price freeze until Q2", "demo of reporting",
    "Harbor Sales pipeline", "enterprise plan Northwind", "answer by Friday", "lars@northwind-b.example",
]


def test_scoped_retrieval_never_returns_another_workspace(db):
    total = leaks = 0
    with as_workspace(db, WS_A) as c:
        for q in ADVERSARIAL:
            hits = retrieve(c, WS_A, q, embedder)
            total += len(hits)
            leaks += sum(h.record_id in B_IDS for h in hits)
    assert total > 0
    assert leaks == 0


def test_second_wall_query_without_filter_still_cannot_see_b(db):
    with as_workspace(db, WS_A) as c:
        rows = c.execute(
            "select record_id::text from embeddings order by embedding <=> (select embedding from embeddings limit 1) limit 50"
        ).fetchall()
    assert rows
    assert not any(r["record_id"] in B_IDS for r in rows)


def test_write_tagged_with_another_workspace_is_rejected(db):
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match="row-level security"):
        with as_workspace(db, WS_A) as c:
            c.execute("insert into tasks values (gen_random_uuid(), %s, 'smuggled task', null, 'open', null, null)", [WS_B])


def test_workspace_b_sees_its_own_northwind_and_only_its_own(db):
    with as_workspace(db, WS_B) as c:
        hits = retrieve(c, WS_B, "Northwind price", embedder)
    assert hits
    assert all(h.record_id in B_IDS for h in hits)
