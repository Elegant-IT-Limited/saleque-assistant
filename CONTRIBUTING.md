# Contributing

Thanks for taking the time. This repository is the reference build behind a published case study, so the bar is: every change keeps the tests green and keeps the code readable by someone who has never seen it.

## Before you start

You need Python 3.10 or newer, [uv](https://docs.astral.sh/uv/), and a scratch PostgreSQL 17 with the pgvector extension. The tests drop and rebuild the `public` schema on every module, so never point `DATABASE_URL` at a database you care about.

```bash
uv sync
cp .env.example .env
uv run ruff check .
uv run lint-imports
uv run pytest -v
```

## Where things go

- A new table goes in a new Alembic revision under `alembic/versions/<module>/`, with `enable_tenant_rls()` from `app/db/rls.py` if it holds workspace data. Write the downgrade too; CI runs upgrade, downgrade and upgrade again.
- SQL lives in the module's `repository.py`. Rules live in `service.py`. Route handlers validate, call a service and return; nothing else.
- Another module's data is reached through its service, never its repository. `lint-imports` fails the build otherwise.
- A new provider or external API is an adapter in `app/integrations/`, and adapters never import from `app/modules/`.

## Sending a change

1. Open an issue first if the change is more than a fix, so we can agree on the shape.
2. Branch from `main`. One change per pull request.
3. Add or update a test for any behaviour you change. The suite never calls a live model; provider replies are recorded in `tests/support/fakes.py` and `tests/integrations/`.
4. Run `ruff check .`, `lint-imports` and `pytest -v`. CI runs the same.
5. Write the commit message as a short imperative subject, then a body that says why. The history in this repository shows the style.

## What we will not merge

- A change that makes any test depend on the network or a live API key.
- A change that reads or writes a tenant table outside `as_workspace`.
- A change that lets a model output reach the user or the database without passing `verify`.
