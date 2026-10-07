import datetime as dt
import json
import re
import tomllib

from . import db, rules
from .connectors.plaid import Plaid, has_items
from .connectors.simplefin import SimpleFIN


def load_config(path="config.toml"):
    with open(path, "rb") as f:
        return tomllib.load(f)


def _now():
    return dt.datetime.now(dt.timezone.utc)


def run(conn, connector):
    """Fetch, upsert raw rows, create normalized rows for new ones. Safe to run repeatedly."""
    started = _now()
    run_id = conn.execute("INSERT INTO sync_runs(connector, started_at, status) VALUES(?,?,'running')",
                          (connector.name, started.isoformat())).lastrowid
    try:
        last = conn.execute("SELECT MAX(last_synced_at) FROM accounts WHERE provider=?",
                            (connector.name,)).fetchone()[0]
        since = (dt.datetime.fromisoformat(last) - dt.timedelta(days=7)).isoformat() if last else None
        accounts, txns, errors = connector.fetch(since)
        ids = {}
        for a in accounts:
            conn.execute("""INSERT INTO accounts(provider, provider_account_id, name, institution) VALUES(?,?,?,?)
                ON CONFLICT(provider, provider_account_id) DO UPDATE SET name=excluded.name, institution=excluded.institution""",
                         (connector.name, a.provider_account_id, a.name, a.institution))
            ids[a.provider_account_id] = conn.execute(
                "SELECT id FROM accounts WHERE provider=? AND provider_account_id=?",
                (connector.name, a.provider_account_id)).fetchone()[0]
        new = 0
        for t in txns:
            acct = ids[t.provider_account_id]
            cur = conn.execute("""INSERT OR IGNORE INTO raw_transactions(account_id, provider, provider_txn_id,
                posted_date, amount_cents, description, pending, payload) VALUES(?,?,?,?,?,?,?,?)""",
                               (acct, connector.name, t.provider_txn_id, t.date, t.amount_cents,
                                t.description, int(t.pending), json.dumps(t.payload)))
            if cur.rowcount:
                new += 1
                conn.execute("""INSERT INTO transactions(raw_id, account_id, date, amount_cents, merchant, category_id)
                    VALUES(?,?,?,?,?,?)""", (cur.lastrowid, acct, t.date, t.amount_cents, t.description,
                                             rules.categorize(conn, t.description)))
        for tid in getattr(connector, "removed", []):  # e.g. pending rows that posted under a new ID
            conn.execute("DELETE FROM transactions WHERE raw_id IN (SELECT id FROM raw_transactions WHERE provider=? AND provider_txn_id=?)", (connector.name, tid))
            conn.execute("DELETE FROM raw_transactions WHERE provider=? AND provider_txn_id=?", (connector.name, tid))
        conn.execute("UPDATE accounts SET last_synced_at=? WHERE provider=?", (started.isoformat(), connector.name))
        conn.execute("UPDATE sync_runs SET finished_at=?, status='ok', new_rows=?, error=? WHERE id=?",
                     (_now().isoformat(), new, "; ".join(map(str, errors)) or None, run_id))
        conn.commit()
        getattr(connector, "commit", lambda: None)()
        return new
    except Exception as e:
        msg = re.sub(r"//[^@/\s]+@", "//***@", str(e))  # never log credentials from the access URL
        conn.execute("UPDATE sync_runs SET finished_at=?, status='error', error=? WHERE id=?",
                     (_now().isoformat(), msg, run_id))
        conn.commit()
        raise


def connectors(cfg):
    out = []
    if cfg.get("simplefin", {}).get("access_url"):
        out.append(SimpleFIN(cfg["simplefin"]["access_url"]))
    if has_items():
        out.append(Plaid(cfg.get("plaid", {})))
    return out


def run_all(conn, cfg):
    new, err = 0, None
    for c in connectors(cfg):
        try:
            new += run(conn, c)
        except Exception as e:
            err = err or e
    if err:
        raise err
    return new


if __name__ == "__main__":
    cfg = load_config()
    conn = db.connect(cfg["app"]["db_path"])
    print("new transactions:", run_all(conn, cfg))
