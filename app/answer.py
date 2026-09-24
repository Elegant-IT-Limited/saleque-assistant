from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .retrieve import Hit


class Sentence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1)
    sources: list[str] = Field(default_factory=list)


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["task", "deal_update", "calendar_hold"]
    title: str
    due: str | None = None
    sources: list[str] = Field(default_factory=list)


class Answer(BaseModel):
    """The only shape a model is allowed to return. Its JSON schema is sent to the provider."""

    model_config = ConfigDict(extra="forbid")
    sentences: list[Sentence]
    actions: list[Action] = Field(default_factory=list, max_length=3)


class CitedSentence(BaseModel):
    text: str
    sources: list[int]


class Verified(BaseModel):
    sentences: list[CitedSentence]
    dropped: list[str]
    actions: list[Action]
    citations: list[Hit]
    not_found: bool


def verify(raw: object, retrieved: list[Hit]) -> Verified:
    """Every cited id must be in the retrieved set. A sentence with no valid source is dropped.

    Citation numbers follow first use, so the UI renders [1] [2] in reading order.
    """
    parsed = Answer.model_validate(raw)
    allowed = {h.record_id: h for h in retrieved}
    order: list[str] = []

    def num(record_id: str) -> int:
        if record_id not in order:
            order.append(record_id)
        return order.index(record_id) + 1

    kept, dropped = [], []
    for s in parsed.sentences:
        ok = [i for i in s.sources if i in allowed]
        if ok:
            kept.append(CitedSentence(text=s.text, sources=[num(i) for i in ok]))
        else:
            dropped.append(s.text)
    actions = [a for a in parsed.actions if a.sources and all(i in allowed for i in a.sources)]
    return Verified(sentences=kept, dropped=dropped, actions=actions,
                    citations=[allowed[i] for i in order], not_found=not kept)
