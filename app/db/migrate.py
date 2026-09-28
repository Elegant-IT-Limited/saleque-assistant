"""Programmatic access to the Alembic migrations, for tests and local scripts."""

from pathlib import Path

import psycopg
from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[2]


def alembic_config(url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def upgrade(url: str) -> None:
    command.upgrade(alembic_config(url), "head")


def reset(url: str) -> None:
    """Drop everything in `public` and migrate from zero. Tests and local dev only."""
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("drop schema if exists public cascade; create schema public;")
    upgrade(url)
