import pydantic
import pytest

from app.core.tenancy import TenantCtx
from app.db.session import as_workspace
from app.modules.ai.service import build_prompt, verify
from app.modules.search.repository import SearchRepository
from app.modules.search.service import SearchService
from tests.support.fakes import FakeCompleter
from tests.support.seed import WS_A, embedder


def test_drops_every_sentence_that_cannot_point_at_a_retrieved_record(db):
    with as_workspace(db, WS_A) as c:
        hits = SearchService(SearchRepository(c), embedder).retrieve(TenantCtx(WS_A), "What did we promise Northwind before the renewal call?")
    v = verify(FakeCompleter().complete(build_prompt("q", hits)).raw, hits)
    assert len(v.sentences) == 5
    assert v.dropped == ["Northwind also asked about an API add-on.", "They mentioned a competitor quote."]
    assert len(v.citations) == 4
    assert len(v.actions) == 3
    assert v.not_found is False


def test_returns_the_not_found_state_when_nothing_can_be_cited():
    v = verify({"sentences": [{"text": "Made up.", "sources": []}], "actions": []}, [])
    assert v.not_found is True
    assert len(v.dropped) == 1


def test_rejects_output_that_is_not_in_the_schema():
    with pytest.raises(pydantic.ValidationError):
        verify({"answer": "free text"}, [])
