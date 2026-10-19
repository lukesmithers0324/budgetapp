"""Inspect and clean up bank connections and duplicate rows (run from the project folder).
  python -m app.items list              saved connections (names only, never tokens)
  python -m app.items report            accounts, and what kind of duplicate rows exist
  python -m app.items dedupe            drop pending rows that already have a posted twin
  python -m app.items remove N --yes    revoke connection N at Plaid and delete its accounts and transactions here
Plaid's Trial plan does not give a removed connection's slot back."""
import sys

from . import db, security, sync
from .connectors import plaid


def drop_accounts(conn, provider_account_ids):
    n = 0
    for pid in provider_account_ids:
        row = conn.execute("SELECT id FROM accounts WHERE provider='plaid' AND provider_account_id=?", (pid,)).fetchone()
        if row:
            n += conn.execute("DELETE FROM transactions WHERE account_id=?", (row[0],)).rowcount
            conn.execute("DELETE FROM raw_transactions WHERE account_id=?", (row[0],))
            conn.execute("DELETE FROM accounts WHERE id=?", (row[0],))
    conn.commit()
    return n


def dedupe_pending(conn):
    rows = conn.execute("""SELECT p.id FROM transactions p JOIN raw_transactions pr ON pr.id=p.raw_id
        WHERE pr.pending=1 AND EXISTS (SELECT 1 FROM transactions q JOIN raw_transactions qr ON qr.id=q.raw_id
          WHERE qr.pending=0 AND q.account_id=p.account_id AND q.amount_cents=p.amount_cents
            AND abs(julianday(q.date)-julianday(p.date))<=5)""").fetchall()
    for r in rows:
        conn.execute("DELETE FROM transactions WHERE id=?", (r["id"],))
    conn.commit()
    return len(rows)


def report(conn):
    for r in conn.execute("SELECT a.id, a.name, a.institution, COUNT(t.id) n FROM accounts a LEFT JOIN transactions t ON t.account_id=a.id GROUP BY a.id"):
        print(f"account {r['id']}: {r['name']} at {r['institution']}: {r['n']} transactions")
    groups = conn.execute("""SELECT COUNT(DISTINCT t.account_id) accts, SUM(r.pending) pend FROM transactions t
        JOIN raw_transactions r ON r.id=t.raw_id GROUP BY t.date, t.amount_cents HAVING COUNT(*)>1""").fetchall()
    cross = sum(1 for g in groups if g["accts"] > 1)
    pend = sum(1 for g in groups if g["accts"] == 1 and g["pend"])
    print(f"{len(groups)} date+amount groups have more than one row: {cross} span several accounts, {pend} include a pending row, {len(groups) - cross - pend} other")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    cfg = sync.load_config()
    conn = db.connect(str(security.home() / cfg["app"]["db_path"]))
    items = plaid._load()
    if cmd == "list":
        for i, it in enumerate(items, 1):
            print(i, it.get("institution") or "unknown bank", it["item_id"][:6])
    elif cmd == "report":
        report(conn)
    elif cmd == "dedupe":
        print("removed", dedupe_pending(conn), "pending duplicates")
    elif cmd == "remove" and len(sys.argv) == 4 and sys.argv[3] == "--yes" and sys.argv[2].isdigit() and 1 <= int(sys.argv[2]) <= len(items):
        n = int(sys.argv[2])
        client, it = plaid.Plaid(cfg.get("plaid", {})), items[n - 1]
        ids = [a["account_id"] for a in client._post("/accounts/get", {"access_token": it["access_token"]})["accounts"]]
        client._post("/item/remove", {"access_token": it["access_token"]})
        plaid._save(items[:n - 1] + items[n:])
        print("removed connection", n, "and", drop_accounts(conn, ids), "transactions")
    else:
        sys.exit(__doc__)
