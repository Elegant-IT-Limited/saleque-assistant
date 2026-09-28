from dataclasses import dataclass
from typing import Literal

RecordType = Literal["lead", "account", "deal", "task", "activity"]

# record type -> the table it lives in; the only place this mapping is spelled out
RECORD_TABLES: dict[str, str] = {"lead": "leads", "account": "accounts", "deal": "deals", "task": "tasks", "activity": "activities"}


@dataclass(frozen=True)
class Hit:
    """One retrieved record: what gets shown to the model and cited back to the user."""

    record_type: str
    record_id: str
    content: str
    score: float
