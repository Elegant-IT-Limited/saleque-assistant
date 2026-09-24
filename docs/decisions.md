# Decisions

Short records of the choices that shaped this build, and what would have to change for us to revisit them.

## 1. Two walls between tenants

Every query the application runs carries a `workspace_id` filter. That is the first wall, and on its own it is what most multi-tenant products rely on. The second is Row Level Security inside Postgres: `as_workspace` in `app/db.py` opens one transaction, switches to `app_user` and sets `app.workspace_id` as a transaction-local setting. From that point the database refuses rows from any other workspace even if a query forgets the filter.

`tests/test_isolation.py` runs 12 adversarial questions with the filter on, then the same search with the filter removed, and expects 0 foreign rows both times. If a future query is written without the filter, that test still passes and the policy still holds.

## 2. Everything lives in Postgres

Embeddings in pgvector, the queue in an outbox table, the answer cache and the AI ledger in ordinary tables. A separate vector database, a broker and a cache cluster would have tripled what a 2-person team has to operate. One database, one backup, one thing to page someone about.

## 3. Re-embed only when the rendered document changes

Each record renders to one paragraph (`app/render.py`). That text is hashed, and a write enqueues an embedding job only when the hash differs from the stored one. Reassigning an owner or moving a stage does not re-embed. The outbox row is written in the same transaction as the record, so there is no window where a record exists without its job. A deleted record takes its embedding with it through a trigger.

## 4. Hybrid retrieval, fused in SQL

Vector search finds "held the price" when the question says "price freeze". It is bad at "$48,000" and at names. Full-text search is the reverse. `app/retrieve.py` runs both in one round trip, scoped to the workspace, and merges them with reciprocal rank fusion inside Postgres. The top 8 records go to the model.

## 5. The answer is a schema, and the verifier has the last word

`Answer` in `app/answer.py` is one Pydantic model. Its JSON schema is what Claude and OpenAI are held to, and the same model validates what comes back, so the contract and the validator cannot drift. `verify` then drops any sentence whose sources were not in the retrieved set and renumbers citations in order of first use. If nothing survives, the answer is the not-found state.

## 6. Claude first, OpenAI when Claude cannot answer

`WithFallback` in `app/providers.py` tries Claude with a forced tool call and moves to OpenAI with a JSON schema response format on a provider outage, rate limit or timeout. The same verifier runs on both. The ledger records which provider actually answered.

## 7. Decisions go to Jev, language goes to Claude and OpenAI

Lead fit, intent and budget are typed questions to Jev (TypeSafe AI), which returns calibrated confidence rather than prose. Below 0.80 confidence on intent the lead goes to a person. A chat model can produce a number, but not a calibrated one, and the same lead can score differently on a retry. `app/jev.py` keeps the routing rule in plain Python anyone on the team can read.

## 8. One door for every model call

`app/ai_service.py` meters each call against the workspace, checks a cache keyed on the workspace, the normalised question, the sorted record ids and the model, routes through the adapter, and refuses before calling a model when credits are out. No feature calls a provider directly.

## 9. Tests run on a real Postgres and never call a live model

Anthropic and OpenAI run through their real SDKs against recorded HTTP payloads. Jev runs through `typesafe_sdk` against recorded System One responses. Postgres is real (17.5 with pgvector 0.8.0). A test failure is always ours.
