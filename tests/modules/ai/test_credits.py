import pytest

from app.core.exceptions import OutOfCredits
from app.core.tenancy import TenantCtx
from app.db.session import as_workspace
from app.modules.ai.repository import AIRepository
from app.modules.ai.service import AIService
from app.modules.search.repository import SearchRepository
from app.modules.search.service import SearchService
from tests.support.fakes import FakeCompleter
from tests.support.seed import WS_A, WS_B, embedder

Q = "What did we promise Northwind before the renewal call?"


def services(conn, completer=None):
    return SearchService(SearchRepository(conn), embedder), AIService(AIRepository(conn), completer or FakeCompleter())


def test_meters_one_credit_on_a_miss_and_zero_on_the_cached_repeat(db):
    ctx = TenantCtx(WS_A)
    with as_workspace(db, WS_A) as c:
        search, ai = services(c)
        hits = search.retrieve(ctx, Q)
        first = ai.ask(ctx, Q, hits)
        # same question, shouted and padded: still the same question
        second = ai.ask(ctx, Q.upper() + "  ", hits)
        balance = ai.credits(ctx)
    assert (first.cache, first.credits) == ("miss", 1)
    assert (second.cache, second.credits) == ("hit", 0)
    assert balance == 199


def test_different_evidence_changes_the_cache_key(db):
    ctx, q = TenantCtx(WS_A), "Renewal status for Northwind"
    with as_workspace(db, WS_A) as c:
        search, ai = services(c)
        hits = search.retrieve(ctx, q)
        first = ai.ask(ctx, q, hits)
        second = ai.ask(ctx, q, hits[:-1])
    assert first.cache == "miss"
    assert second.cache == "miss"


def test_refuses_before_calling_a_model_when_credits_run_out(db):
    calls = []

    class Counting(FakeCompleter):
        def complete(self, prompt):
            calls.append(prompt)
            return super().complete(prompt)

    ctx = TenantCtx(WS_B)
    with as_workspace(db, WS_B) as c:
        # spend the whole allowance in one ledger row
        AIRepository(c).record_usage(ctx, "assistant.ask", "test", "fake-structured-1", 0, 0, "miss", 200)
        search, ai = services(c, Counting())
        with pytest.raises(OutOfCredits):
            ai.ask(ctx, "Northwind price", search.retrieve(ctx, "Northwind price"))
    assert calls == []
