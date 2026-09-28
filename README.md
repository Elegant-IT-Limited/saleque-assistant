# saleque-assistant

The AI service behind the SaleQue CRM assistant: a multi-tenant RAG layer on PostgreSQL and pgvector that answers only from a workspace's own records, cites every sentence, and meters every model call. This is the reference build for the case study at [eleganttechbd.com/works/saleque-ai-crm-rag-assistant](https://eleganttechbd.com/works/saleque-ai-crm-rag-assistant). Every code block and terminal capture on that page is generated from this repository.

Python 3.10+, FastAPI, psycopg 3, PostgreSQL 17 with pgvector 0.8 and Row Level Security, Alembic, a Pydantic answer contract, Claude and OpenAI behind one adapter, Jev (TypeSafe AI) for lead scoring and routing.

## Layout

The service is a modular monolith. Each module owns its tables and exposes a service; other modules call that service and never reach into its repository. The rule is checked in CI by import-linter (see `[tool.importlinter]` in `pyproject.toml`).

```
alembic/versions/<area>/     one folder per owner (core and crm hold the shared and CRM-record tables), so a reviewer sees where a schema change belongs
app/
├── main.py                  composition root: builds the app and wires the real clients
├── api/internal.py          aggregates the module routes under /api/internal
├── core/                    config, session tokens, tenant context, dependency providers, error handlers, router registry
├── db/                      connection, the per-request tenant scope, the shared RLS policy, migration helpers
├── integrations/            provider adapters: Claude and OpenAI, embeddings, Jev
├── workers/tasks/           background jobs; today, draining the embedding outbox
└── modules/
    ├── search/              renders records to documents, keeps embeddings current, hybrid retrieval
    ├── ai/                  the single door to every model call: prompt, verifier, cache, credits, ledger
    └── lead/                lead scoring questions for Jev and the routing rule
tests/
├── api/                     endpoint tests through the FastAPI app
├── modules/                 per-module tests against a real Postgres
├── workers/                 the embedding lifecycle
├── integrations/            the real Anthropic and OpenAI SDKs against recorded payloads
└── support/                 seed data, recorded clients, the deterministic test embedder
scripts/                     explain (EXPLAIN ANALYZE and the RLS proof), ask, score_leads
docs/decisions.md            why it is built this way
docs/captures/               terminal output the case study page is generated from
```

Each module keeps the same surface: `schemas.py`, `repository.py` (SQL only, no rules), `service.py` (the rules, and the only thing other modules import), `dependencies.py`, and `api/internal.py` where the module has routes. Data access is plain SQL through psycopg rather than an ORM, because the parts of this service that matter most (RLS, the pgvector operators, the fused ranking query) read best as SQL.

## Run it

```bash
uv sync
cp .env.example .env              # DATABASE_URL must point at a scratch Postgres 17 with pgvector
uv run alembic upgrade head
uv run pytest -v                  # 28 tests, real Postgres, no network
uv run python -m scripts.explain  # EXPLAIN ANALYZE on the scoped search, plus the second wall
uv run python -m scripts.ask      # one question through retrieval, the answer contract, verifier, cache, ledger
uv run python -m scripts.score_leads   # Jev decisions per lead, on recorded System One replies
uv run uvicorn app.main:create_app --factory   # needs SESSION_SECRET (32+ chars) and the provider keys in .env
```

The tests and scripts drop and rebuild the `public` schema. Do not point `DATABASE_URL` at anything you care about. The scripts use the recorded clients from `tests/support`, so they run offline too.

Routes: `POST /api/internal/assistant/ask` and `POST /api/internal/leads/{lead_id}/score`, both behind a session token.

## What the tests prove

- Workspace A can never retrieve a workspace B record, with the filter on and with it removed (`tests/modules/search/test_isolation.py`)
- A row tagged with another workspace is rejected by the policy, and a workspace can read only its own `workspaces` row and delete none
- Metadata edits do not re-embed; a content edit re-embeds exactly once; a deleted record leaves no embedding (`tests/workers/test_embeddings.py`)
- Sentences with no valid source never render; off-schema output is rejected (`tests/modules/ai/test_verifier.py`)
- Repeat questions cost 0, changed evidence costs 1, an expired answer is regenerated, and a workspace at 0 credits is refused before any model is called (`tests/modules/ai/test_credits.py`)
- Claude is held to the schema, a 529 from Claude falls back to OpenAI under the same contract, and a 400 is raised rather than hidden behind the fallback (`tests/integrations/test_ai_provider.py`)
- Low-confidence leads go to a person, noise is archived, every decision is stored and metered (`tests/modules/lead/test_scoring.py`)
- The body cannot choose the workspace, a forged session is a 401, another workspace's lead is a 404 (`tests/api/`)

Tests never call a live model. Anthropic and OpenAI run through their real SDKs against recorded HTTP payloads. Jev runs through `typesafe_sdk` against recorded System One responses. The captures in `docs/captures/` come from PostgreSQL 17.5 with pgvector 0.8.0.

## License

MIT. See `LICENSE`.
