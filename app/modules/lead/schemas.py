from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel


@dataclass(frozen=True)
class Route:
    """Where a scored lead goes next: a salesperson, customer success, a person to review it, or nowhere."""

    owner: Literal["sales", "success", "review", "archived"]
    priority: Literal["high", "normal"]


class ScoreOut(BaseModel):
    owner: str
    priority: str
    fit: float
    intent: str
    confidence: float
    model: str
