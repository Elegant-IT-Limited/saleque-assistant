"""Embedding adapters.

The vector column is vector(1536), so every embedder behind this interface must
return exactly DIMS floats. Changing models means a migration and a full re-embed,
not a config flag.
"""

from typing import Protocol

DIMS = 1536


class Embedder(Protocol):
    model: str

    def embed(self, text: str) -> list[float]: ...


class OpenAIEmbedder:
    """Production embedder: text-embedding-3-small, 1536 dimensions."""

    def __init__(self, client, model: str = "text-embedding-3-small") -> None:
        self.client, self.model = client, model

    def embed(self, text: str) -> list[float]:
        return self.client.embeddings.create(model=self.model, input=text).data[0].embedding


def to_vec(v: list[float]) -> str:
    """pgvector's text input format. Six decimals is below the noise of any real embedding."""
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"
