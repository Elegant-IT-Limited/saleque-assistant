import hashlib
import math
import re
from typing import Protocol

DIMS = 1536


class Embedder(Protocol):
    model: str

    def embed(self, text: str) -> list[float]: ...


class OpenAIEmbedder:
    """Production embedder. 1536 dimensions, matching vector(1536) in the schema."""

    def __init__(self, client, model: str = "text-embedding-3-small") -> None:
        self.client, self.model = client, model

    def embed(self, text: str) -> list[float]:
        return self.client.embeddings.create(model=self.model, input=text).data[0].embedding


class HashingEmbedder:
    """Deterministic feature-hashing embedder for tests and CI.

    Same input, same vector, no network. It sits behind the same interface as the
    provider embedder, so everything above it runs unchanged.
    """

    model = "hashing-1536-v1"

    def embed(self, text: str) -> list[float]:
        v = [0.0] * DIMS
        toks = [t for t in re.sub(r"[^a-z0-9$.]+", " ", text.lower()).split(" ") if t]
        for g in toks + [a + "_" + b for a, b in zip(toks, toks[1:], strict=False)]:
            h = hashlib.sha1(g.encode()).digest()
            v[int.from_bytes(h[:4], "big") % DIMS] += 1.0 if h[4] & 1 else -1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]


def to_vec(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"
