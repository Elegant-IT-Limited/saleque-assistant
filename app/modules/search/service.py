"""Search: keeping embeddings in step with records, and retrieving the records a question needs."""

import hashlib

from app.core.tenancy import TenantCtx
from app.integrations.embeddings import Embedder, to_vec
from app.modules.search.documents import render_document
from app.modules.search.repository import SearchRepository
from app.modules.search.schemas import Hit, RecordType


class SearchService:
    def __init__(self, repo: SearchRepository, embedder: Embedder) -> None:
        self.repo, self.embedder = repo, embedder

    def retrieve(self, ctx: TenantCtx, question: str, k: int = 8) -> list[Hit]:
        """Top k records for a question, scoped to the caller's workspace."""
        return self.repo.hybrid(ctx, to_vec(self.embedder.embed(question)), question, k)

    def enqueue_if_changed(self, ctx: TenantCtx, kind: RecordType, record_id: str) -> bool:
        """Call inside the write transaction. Enqueues only when the rendered document changed.

        Most CRM edits (owner, stage, a timestamp) do not change what the record says,
        and re-embedding them would be pure cost. Writing the outbox row in the same
        transaction as the record means there is no moment where the record exists
        and its embedding job does not.
        """
        row = self.repo.record(kind, record_id)
        if row is None:
            return False
        digest = hashlib.sha256(render_document(kind, row).encode()).digest()
        if self.repo.stored_hash(kind, record_id) == digest:
            return False
        self.repo.enqueue(ctx, kind, record_id)
        return True

    def embed_pending(self, ctx: TenantCtx, batch: int = 100) -> int:
        """Worker side: claim pending rows, embed, upsert, mark done. Returns rows handled."""
        pending = self.repo.claim_pending(batch)
        for p in pending:
            row = self.repo.record(p["record_type"], p["record_id"])
            # the record may have been deleted after it was enqueued; the delete
            # trigger already removed its embedding, so there is nothing to write
            if row is not None:
                doc = render_document(p["record_type"], row)
                self.repo.upsert_embedding(ctx, p["record_type"], p["record_id"], doc,
                                           hashlib.sha256(doc.encode()).digest(),
                                           self.embedder.model, to_vec(self.embedder.embed(doc)))
            self.repo.mark_processed(p["id"])
        return len(pending)
