# saleque-assistant

The AI service behind the SaleQue CRM assistant: a multi-tenant RAG layer on PostgreSQL and pgvector that answers only from a workspace's own records, cites every sentence, and meters every model call. This is the reference build for the case study at [eleganttechbd.com/works/saleque-ai-crm-rag-assistant](https://eleganttechbd.com/works/saleque-ai-crm-rag-assistant). Every code block and terminal capture on that page is generated from this repository.

Python 3.10+, FastAPI, psycopg 3, PostgreSQL 17 with pgvector 0.8 and Row Level Security, a Pydantic answer contract, Claude and OpenAI behind one adapter, Jev (TypeSafe AI) for lead scoring and routing.

## Layout

```
sql/schema.sql       every table, RLS on all of them, HNSW and GIN indexes, the embedding-cleanup trigger
app/db.py            one transaction, one role, one workspace per request
app/render.py        each record type rendered to the paragraph that gets embedded and cited
app/embed.py         provider embedder and the deterministic hashing embedder used by tests
app/outbox.py        change-only embeddings, SKIP LOCKED worker
app/retrieve.py      hybrid vector + full text search, reciprocal rank fusion, one round trip
app/answer.py        the answer schema and the citation verifier
app/providers.py     Claude (forced tool call), OpenAI (json_schema), fallback on provider errors
app/ai_service.py    meter, cache, route, refuse: the only door to a model
app/jev.py           lead fit, intent and budget as typed answers, with a confidence gate
app/api.py           FastAPI routes; the workspace comes from the signed session, never the body
scripts/             explain (EXPLAIN ANALYZE and the RLS proof), ask, score_leads
tests/               8 suites, 25 tests, on a real Postgres, no network
docs/decisions.md    why it is built this way
docs/captures/       terminal output the case study page is generated from
```

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # DATABASE_URL must point at a scratch Postgres 17 with pgvector
pytest -v                       # 25 tests, real Postgres, no network
python -m scripts.explain       # EXPLAIN ANALYZE on the scoped search, plus the second wall
python -m scripts.ask           # one question through retrieval, provider, verifier, cache, ledger
python -m scripts.score_leads   # Jev decisions per lead
```

The tests and scripts drop and rebuild the `public` schema. Do not point `DATABASE_URL` at anything you care about.

## What the tests prove

- Workspace A can never retrieve a workspace B record, with the filter on and with it removed (`test_isolation.py`)
- A row tagged with another workspace is rejected by the policy
- Metadata edits do not re-embed; a content edit re-embeds exactly once; a deleted record leaves no embedding (`test_lifecycle.py`)
- Sentences with no valid source never render; off-schema output is rejected (`test_contract.py`)
- Repeat questions cost 0, changed evidence costs 1, and a workspace at 0 credits is refused before any model is called (`test_ledger.py`)
- Claude is held to the schema, and a 529 from Claude falls back to OpenAI under the same contract (`test_providers.py`)
- Low-confidence leads go to a person, noise is archived, every decision is stored and metered (`test_jev.py`)
- The body cannot choose the workspace, a forged session is a 401, another workspace's lead is a 404 (`test_api.py`)

Tests never call a live model. Anthropic and OpenAI run through their real SDKs against recorded HTTP payloads. Jev runs through `typesafe_sdk` against recorded System One responses. The captures in `docs/captures/` come from PostgreSQL 17.5 with pgvector 0.8.0.

## License

MIT. See `LICENSE`.
