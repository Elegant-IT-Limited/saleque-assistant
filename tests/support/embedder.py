import hashlib
import math
import re

from app.integrations.embeddings import DIMS


class HashingEmbedder:
    """Deterministic feature-hashing embedder for tests and CI.

    Same input, same vector, no network. It sits behind the same Embedder interface
    as the provider, so everything above it runs unchanged. It is good enough to
    rank by shared words and word pairs, which is all the retrieval tests need.
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
