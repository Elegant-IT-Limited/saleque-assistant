from datetime import date, datetime
from typing import Any, Literal

RecordType = Literal["lead", "account", "deal", "task", "activity"]
TABLE: dict[str, str] = {"lead": "leads", "account": "accounts", "deal": "deals", "task": "tasks", "activity": "activities"}


def _s(r: dict[str, Any], key: str) -> str:
    v = r.get(key)
    if v is None:
        return ""
    if isinstance(v, (date, datetime)):
        return v.isoformat()[:10]
    return str(v)


def _opt(prefix: str, value: str, suffix: str = "") -> str:
    return f"{prefix}{value}{suffix}" if value else ""


def render_document(kind: RecordType, r: dict[str, Any]) -> str:
    """Each record renders to one readable paragraph. This text is what gets embedded and cited."""
    s = lambda k: _s(r, k)  # noqa: E731
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
