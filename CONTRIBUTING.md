# Contributing

Thanks for taking the time. This repository is the reference build behind a published case study, so the bar is: every change keeps the tests green and keeps the code readable by someone who has never seen it.

## Before you start

You need Python 3.10 or newer and a scratch PostgreSQL 17 with the pgvector extension. The tests drop and rebuild the `public` schema on every module, so never point `DATABASE_URL` at a database you care about.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
ruff check .
pytest -v
```

## Sending a change

1. Open an issue first if the change is more than a fix, so we can agree on the shape.
2. Branch from `main`. One change per pull request.
3. Add or update a test for any behaviour you change. The suite never calls a live model or Graph endpoint; provider replies are recorded in `tests/fakes.py`.
4. Run `ruff check .` and `pytest -v`. CI runs the same.
5. Write the commit message as a short imperative subject, then a body that says why. The history in this repository shows the style.

## What we will not merge

- A change that makes any test depend on the network or a live API key.
- A change that reads or writes a tenant table without going through `as_workspace`.
- A change that lets a model output reach the database without passing `verify`.
