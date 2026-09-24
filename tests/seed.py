from app.db import as_workspace
from app.embed import HashingEmbedder
from app.outbox import drain_outbox, enqueue_if_changed

WS_A = "4f2a6c1e-8b3d-4e7a-9c21-0d5f7a3b9e11"
WS_B = "b7e1d2c3-4a5f-4b6e-8c9d-1e2f3a4b5c6d"
ID = {
    "acctA": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "dealA": "3f2504e0-4f89-41d3-9a0c-0305e82c3301",
    "emailA": "9b2d5f6a-1c3e-4d8f-b7a2-6e5c4d3b2a19",
    "noteA": "e1d2c3b4-a596-4877-9a0b-1c2d3e4f5a6b",
    "taskA": "c56a4180-65aa-42ec-a945-5fd21dec0538",
    "leadA": "16fd2706-8baf-433b-82eb-8c7fada847da",
    "leadVague": "5e8b1c2d-3f4a-4b5c-9d6e-7f8a9b0c1d2e",
    "leadSpam": "0c1d2e3f-4a5b-4c6d-8e7f-9a0b1c2d3e4f",
    "acctB": "a3bb189e-8bf9-4888-9912-ace4e6543002",
    "dealB": "6ba7b810-9dad-41d1-80b4-00c04fd430c8",
    "noteB": "1b4e28ba-2fa1-41d2-883f-0016d3cca427",
    "leadB": "886313e1-3b8a-4372-9b90-0c9aee199e5d",
}
B_IDS = {ID["acctB"], ID["dealB"], ID["noteB"], ID["leadB"]}
embedder = HashingEmbedder()


def seed(conn) -> None:
    conn.execute(
        "insert into workspaces values (%s, 'A Workspace', %s), (%s, 'Harbor Sales', %s)",
        [WS_A, "B2B software teams of 10 to 200 people with a funded roadmap", WS_B, "Manufacturing groups in the EU"],
    )
    with as_workspace(conn, WS_A) as c:
        c.execute("insert into accounts values (%s,%s,'Northwind','northwind.example','Team','Logistics software, 40 seats, renewal every September.')", [ID["acctA"], WS_A])
        c.execute("insert into deals values (%s,%s,%s,'Northwind renewal',4800000,'Negotiation','2026-09-30','Annual renewal. Price held at $48,000 for 12 months.')", [ID["dealA"], WS_A, ID["acctA"]])
        c.execute("insert into activities values (%s,%s,'email','Pricing confirmation to Maya Chen','Confirmed the renewal price is held at $48,000 for 12 months, no uplift this cycle.',%s,'2026-09-09T10:12:00Z')", [ID["emailA"], WS_A, ID["acctA"]])
        c.execute("insert into activities values (%s,%s,'note','Call notes: renewal scope','Call with Maya Chen. Agreed two extra seats included at no charge. She asked for the updated SOW before the 20th.',%s,'2026-09-12T15:30:00Z')", [ID["noteA"], WS_A, ID["acctA"]])
        c.execute("insert into tasks values (%s,%s,'Send updated SOW to Maya Chen','2026-09-20','open','Sam',%s)", [ID["taskA"], WS_A, ID["dealA"]])
        c.execute("insert into leads values (%s,%s,'Daniel Reyes','Tallyroom','daniel@tallyroom.example','qualified','Raised a pre-seed, wants an MVP next month.')", [ID["leadA"], WS_A])
        c.execute("insert into leads values (%s,%s,'Priya Nair','Oakline','priya@oakline.example','new','Saw the site. Might need something later, not sure what yet.')", [ID["leadVague"], WS_A])
        c.execute("insert into leads values (%s,%s,'SEO Growth Team',null,'offers@seo-growth.example','new','We can get you to page one of Google in 30 days.')", [ID["leadSpam"], WS_A])
        for kind, key in [("account", "acctA"), ("deal", "dealA"), ("activity", "emailA"), ("activity", "noteA"), ("task", "taskA"), ("lead", "leadA")]:
            enqueue_if_changed(c, WS_A, kind, ID[key])
        drain_outbox(c, WS_A, embedder)
    with as_workspace(conn, WS_B) as c:
        c.execute("insert into accounts values (%s,%s,'Northwind','northwind-b.example','Enterprise','Different Northwind. Manufacturing group in Rotterdam.')", [ID["acctB"], WS_B])
        c.execute("insert into deals values (%s,%s,%s,'Northwind expansion',4800000,'Proposal','2026-10-15','Expansion to 120 seats. Price freeze requested by Lars Petersen.')", [ID["dealB"], WS_B, ID["acctB"]])
        c.execute("insert into activities values (%s,%s,'note','Price freeze discussion','Lars Petersen asked for a price freeze until Q2. We promised an answer by Friday.',%s,'2026-09-11T09:00:00Z')", [ID["noteB"], WS_B, ID["acctB"]])
        c.execute("insert into leads values (%s,%s,'Lars Petersen','Northwind','lars@northwind-b.example','contacted','Wants a demo of reporting.')", [ID["leadB"], WS_B])
        for kind, key in [("account", "acctB"), ("deal", "dealB"), ("activity", "noteB"), ("lead", "leadB")]:
            enqueue_if_changed(c, WS_B, kind, ID[key])
        drain_outbox(c, WS_B, embedder)
