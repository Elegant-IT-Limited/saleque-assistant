"""The answer contract.

Answer is the only shape a model is allowed to return. Its JSON schema is what the
providers are held to, and the same class validates what comes back, so the
contract and the validator cannot drift apart.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.search.schemas import Hit


class Sentence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1)
    sources: list[str] = Field(default_factory=list)  # record ids, checked by verify()


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["task", "deal_update", "calendar_hold"]
    title: str
    due: str | None = None
    sources: list[str] = Field(default_factory=list)


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sentences: list[Sentence]
    # capped at three so the suggestions stay reviewable at a glance
    actions: list[Action] = Field(default_factory=list, max_length=3)


class CitedSentence(BaseModel):
    text: str
    sources: list[int]  # citation numbers, [1] [2] in reading order


class Verified(BaseModel):
    sentences: list[CitedSentence]
    dropped: list[str]
    actions: list[Action]
    citations: list[Hit]
    not_found: bool


class AskResult(Verified):
    cache: Literal["hit", "miss"]
    credits: int


class AskIn(BaseModel):
    # extra="forbid": a smuggled workspace_id is a 422, never a silent override
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=500)
