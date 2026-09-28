# Decisions

Short records of the choices that shaped this build, and what would have to change for us to revisit them.

## 1. Two walls between tenants

The retrieval queries carry a `workspace_id` filter. That is the first wall, and on its own it is what most multi-tenant products rely on. The second is Row Level Security inside Postgres: `as_workspace` in `app/db/session.py` opens one transaction on a connection of the request's own, switches to `app_user` and sets `app.workspace_id` as a transaction-local setting. From that point the database refuses rows from any other workspace, for every statement, filtered or not. Several repository queries (a record by id, the outbox claim, the cache lookup) rely on that second wall alone, deliberately: it is the one that cannot be forgotten.

`tests/modules/search/test_isolation.py` runs 12 adversarial questions with the filter on, then a raw nearest-neighbour query with no filter at all, and expects 0 foreign rows both times. It also checks that a write tagged with another workspace is rejected, and that a workspace can read only its own `workspaces` row and delete none.

## 2. Everything lives in Postgres

Embeddings in pgvector, the queue in an outbox table, the answer cache and the AI ledger in ordinary tables. A separate vector database, a broker and a cache cluster would each be one more system for a small team to run, secure and back up. One database, one backup, one thing to page someone about.

## 3. Re-embed only when the rendered document changes

Each record renders to one paragraph (`app/modules/search/documents.py`). That text is hashed, and a write enqueues an embedding job only when the hash differs from the stored one. A write that does not change the rendered text (a timestamp, an internal id, a field the document leaves out) does not re-embed, and two edits before the worker runs cost one embedding, not two. The outbox row is written in the same transaction as the record, so there is no window where a record exists without its job. A deleted record takes its embedding with it through a trigger.

## 4. Hybrid retrieval, fused in SQL

Vector search finds "held the price" when the question says "price freeze". It is bad at "$48,000" and at names. Full-text search is the reverse. `SearchRepository.hybrid` in `app/modules/search/repository.py` runs both in one round trip, scoped to the workspace, and merges them with reciprocal rank fusion inside Postgres. The top 8 records go to the model.

## 5. The answer is a schema, and the verifier has the last word

`Answer` in `app/modules/ai/schemas.py` is one Pydantic model. Its JSON schema is what Claude and OpenAI are held to, and the same model validates what comes back, so the contract and the validator cannot drift. `verify` in `app/modules/ai/service.py` then drops any sentence whose sources were not in the retrieved set and renumbers citations in order of first use. If nothing survives, the answer is the not-found state.

## 6. Claude first, OpenAI when Claude cannot answer

`WithFallback` in `app/integrations/ai_provider.py` tries Claude with a forced tool call and moves to OpenAI with a JSON schema response format on a provider outage, rate limit or timeout. The same verifier runs on both. The ledger records which provider actually answered.

## 7. Decisions go to Jev, language goes to Claude and OpenAI

Lead fit, intent and budget are typed questions to Jev (TypeSafe AI), which returns calibrated confidence rather than prose. Below 0.80 confidence on intent the lead goes to a person. A chat model can produce a number, but not a calibrated one, and the same lead can score differently on a retry. `app/modules/lead/service.py` keeps the routing rule in plain Python anyone on the team can read.

## 8. One door for every model call

`AIService` in `app/modules/ai/service.py` meters each call against the workspace, checks a cache keyed on the workspace, the normalised question, the sorted record ids with a hash of each record's text, and the model, routes through the adapter, and refuses before calling a model when credits are out. No feature calls a provider directly.

## 9. Tests run on a real Postgres and never call a live model

Anthropic and OpenAI run through their real SDKs against recorded HTTP payloads. Jev runs through `typesafe_sdk` against recorded System One responses. Postgres is real: PostgreSQL 17 with pgvector, from the `pgvector/pgvector:pg17` image in CI. A test failure is always ours.

## 10. A modular monolith, with the boundaries checked by a tool

The service follows the same module layout as the SaleQue backend: each module owns its tables, its SQL and its rules, and other modules only ever call its service. Lead scoring asks the ai module for a decision; it does not open the ledger itself. The boundaries are import-linter contracts in `pyproject.toml`, so a shortcut across modules fails CI rather than waiting for someone to notice it in review. If a module ever needs to become its own service, the service class is already the seam.

## 11. Migrations are SQL, per area

Alembic runs the migrations, but each revision is written as SQL rather than generated from ORM models. The schema's most important parts (RLS policies, the HNSW index, the delete trigger) are exactly the parts autogenerate cannot see. Revisions live in one folder per area (core, crm, and one per module), and CI applies, rolls back and reapplies the full chain on every push.
