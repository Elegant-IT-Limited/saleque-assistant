"""Score every lead in a workspace with Jev and print the route each one takes."""

import os

from app.db import as_workspace, connect, reset
from app.jev import AUTO, score_lead
from tests.fakes import fake_jev
from tests.seed import WS_A, seed

dim, bold = (lambda s: f"\x1b[2m{s}\x1b[0m"), (lambda s: f"\x1b[1m{s}\x1b[0m")
green, yellow, cyan = (lambda s: f"\x1b[32m{s}\x1b[0m"), (lambda s: f"\x1b[33m{s}\x1b[0m"), (lambda s: f"\x1b[36m{s}\x1b[0m")

conn = connect(os.environ["DATABASE_URL"])
reset(conn)
seed(conn)
jev = fake_jev()  # recorded System One responses; set TYPESAFE_API_KEY and use TypeSafeClient() for live calls

print(bold("score-leads") + dim(f"  model=jev-1.13  auto>={AUTO}  ws {WS_A[:8]}") + "\n")
with as_workspace(conn, WS_A) as c:
    for lead in c.execute("select id::text, name from leads order by name").fetchall():
        route, res = score_lead(c, WS_A, lead["id"], jev)
        i, f, b = res.choices["intent"], res.scores["fit"], res.nouls["has_budget"]
        where = f"{route.owner}/{route.priority}" if route.owner == "sales" else route.owner
        color = yellow if route.owner == "review" else dim if route.owner == "archived" else green
        print(f"  {cyan(lead['id'][:8])}  {lead['name']:<16} {i.choice:<11} {i.confidence:.2f}  fit {f.score:.2f}  budget {b.noul:.2f}  -> {color(where)}")
    n = c.execute("select count(*) as n, sum(input_tokens + output_tokens) as t from ai_ledger where feature = 'lead.score'").fetchone()
print("\n" + dim(f"ledger  feature=lead.score provider=typesafe calls={n['n']} tokens={n['t']}  stored in lead_scores, scoped by RLS"))
