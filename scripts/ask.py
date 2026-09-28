"""One question through the full path: scoped retrieval, provider call, verifier, cache, ledger."""

import os
import sys
import time

from app.core.tenancy import TenantCtx
from app.db.migrate import reset
from app.db.session import as_workspace, connect
from app.modules.ai.repository import AIRepository
from app.modules.ai.service import AIService
from app.modules.search.repository import SearchRepository
from app.modules.search.service import SearchService
from tests.support.fakes import FakeCompleter
from tests.support.seed import WS_A, embedder, seed

dim, bold = (lambda s: f"\x1b[2m{s}\x1b[0m"), (lambda s: f"\x1b[1m{s}\x1b[0m")
pink, green, yellow = (lambda s: f"\x1b[35m{s}\x1b[0m"), (lambda s: f"\x1b[32m{s}\x1b[0m"), (lambda s: f"\x1b[33m{s}\x1b[0m")

q = sys.argv[1] if len(sys.argv) > 1 else "What did we promise Northwind before the renewal call?"
url = os.environ["DATABASE_URL"]
reset(url)
conn = connect(url)
seed(conn)
completer = FakeCompleter()  # swap for WithFallback(ClaudeCompleter(...), OpenAICompleter(...)) to go live
ctx = TenantCtx(WS_A)

with as_workspace(conn, WS_A) as c:
    search, ai = SearchService(SearchRepository(c), embedder), AIService(AIRepository(c), completer)
    t0 = time.perf_counter()
    hits = search.retrieve(ctx, q)
    t1 = time.perf_counter()
    a = ai.ask(ctx, q, hits)
    t2 = time.perf_counter()
    print(bold("ask") + "  " + dim(f"ws {WS_A[:8]} · {len(hits)} records retrieved in {(t1 - t0) * 1000:.0f} ms · answer {a.cache} in {(t2 - t1) * 1000:.0f} ms"))
    print(dim("q   ") + q + "\n")
    for s in a.sentences:
        print("  " + s.text + " " + pink("".join(f"[{n}]" for n in s.sources)))
    if a.dropped:
        print()
        for d in a.dropped:
            print("  " + yellow("dropped") + dim(f"  {d}  (no source in retrieved set)"))
    print("\n" + dim("sources"))
    for i, h in enumerate(a.citations, 1):
        text = h.content if len(h.content) <= 78 else h.content[:78] + "…"
        print(f"  {pink(f'[{i}]')} {h.record_type:<8} {dim(h.record_id[:8])}  {text}")
    print("\n" + dim("proposed actions"))
    for x in a.actions:
        print(f"  {green('•')} {x.type:<13} {x.title}" + (dim(f"  due {x.due}") if x.due else ""))
    print("\n" + dim(f"ledger  feature=assistant.ask provider={completer.provider} cache={a.cache} credits={a.credits}  balance={ai.credits(ctx)}"))
