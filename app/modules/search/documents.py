"""Each CRM record renders to one readable paragraph.

This text is what gets embedded, what the model reads, and what the user sees
behind a citation, so it is written for a person first. Fields that do not change
the meaning (updated_at, owner ids) are left out on purpose: editing them must not
trigger a re-embed.
"""

from datetime import date, datetime
from typing import Any

from app.modules.search.schemas import RecordType


def render_document(kind: RecordType, r: dict[str, Any]) -> str:
    s = lambda k: _text(r, k)  # noqa: E731
    match kind:
        case "lead":
            return f"Lead {s('name')}{_opt(' at ', s('company'))}. Stage {s('stage')}. {s('notes')}".strip()
        case "account":
            return f"Account {s('name')}{_opt(' (', s('domain'), ')')}{_opt(', plan ', s('plan'))}. {s('notes')}".strip()
        case "deal":
            return f"Deal {s('title')}, {money(r['amount_cents'])}, stage {s('stage')}{_opt(', closes ', s('close_date'))}. {s('notes')}".strip()
        case "task":
            return f"Task {s('title')}, {s('status')}{_opt(', due ', s('due_date'))}{_opt(', owner ', s('assignee'))}."
        case "activity":
            return f"{s('kind').capitalize()} on {s('occurred_at')[:10]}: {s('subject')}. {s('body')}".strip()


def money(cents: int) -> str:
    return f"${cents / 100:,.0f}"


def _text(r: dict[str, Any], key: str) -> str:
    v = r.get(key)
    if v is None:
        return ""
    if isinstance(v, (date, datetime)):
        # dates only; a timestamp would make identical content hash differently
        return v.isoformat()[:10]
    return str(v)


def _opt(prefix: str, value: str, suffix: str = "") -> str:
    return f"{prefix}{value}{suffix}" if value else ""
