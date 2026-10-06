import datetime as dt

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import db, sync
from .connectors.simplefin import SimpleFIN

cfg = sync.load_config()
conn = db.connect(cfg["app"]["db_path"])
app = FastAPI(title="Budget")


def _month(m):
    return m or dt.date.today().strftime("%Y-%m")


@app.get("/api/summary")
def summary(month: str | None = None):
    month = _month(month)
    one = lambda sql: conn.execute(sql, (month,)).fetchone()[0] or 0
    base = "FROM transactions WHERE substr(date,1,7)=? AND is_transfer=0 AND amount_cents"
    income = one(f"SELECT SUM(amount_cents) {base}>0")
    spent = -one(f"SELECT SUM(amount_cents) {base}<0")
    cats = conn.execute("""SELECT COALESCE(c.name,'Uncategorized') AS category, -SUM(t.amount_cents) AS spent_cents,
        b.amount_cents AS budget_cents FROM transactions t
        LEFT JOIN categories c ON c.id=t.category_id
        LEFT JOIN budgets b ON b.category_id=t.category_id AND b.month=(
          SELECT MAX(month) FROM budgets WHERE category_id=t.category_id AND month<=?)
        WHERE substr(t.date,1,7)=? AND t.is_transfer=0 AND t.amount_cents<0
        GROUP BY 1 ORDER BY spent_cents DESC""", (month, month)).fetchall()
    cats = [dict(r) for r in cats]
    have = {c["category"] for c in cats}
    bud = {r["name"]: r["amount_cents"] for r in conn.execute("""SELECT c.name, b.amount_cents FROM budgets b
        JOIN categories c ON c.id=b.category_id WHERE b.month=(
          SELECT MAX(month) FROM budgets WHERE category_id=b.category_id AND month<=?)""", (month,))}
    for r in conn.execute("SELECT name FROM categories WHERE kind='expense'"):
        if r["name"] not in have:
            cats.append({"category": r["name"], "spent_cents": 0, "budget_cents": bud.get(r["name"])})
    return {"month": month, "income_cents": income, "spent_cents": spent, "categories": cats}


@app.get("/api/transactions")
def transactions(month: str | None = None, limit: int = 300):
    rows = conn.execute("""SELECT t.id, t.date, t.merchant, c.name AS category, t.amount_cents
        FROM transactions t LEFT JOIN categories c ON c.id=t.category_id
        WHERE substr(t.date,1,7)=? ORDER BY t.date DESC, t.id DESC LIMIT ?""", (_month(month), limit)).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/sync")
def run_sync(force: bool = False):
    """Called when the dashboard opens; only syncs if the last sync is stale."""
    last = conn.execute("SELECT MAX(last_synced_at) FROM accounts").fetchone()[0]
    stale = dt.timedelta(hours=cfg["app"].get("sync_stale_hours", 12))
    if last and not force and dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(last) < stale:
        return {"skipped": True}
    return {"new": sync.run_all(conn, cfg)}


from fastapi import HTTPException  # noqa: E402
from pydantic import BaseModel  # noqa: E402


@app.get("/api/trends")
def trends(months: int = 6):
    rows = conn.execute("""SELECT substr(date,1,7) AS month,
        SUM(CASE WHEN amount_cents>0 THEN amount_cents ELSE 0 END) AS income_cents,
        -SUM(CASE WHEN amount_cents<0 THEN amount_cents ELSE 0 END) AS spent_cents
        FROM transactions WHERE is_transfer=0 GROUP BY 1 ORDER BY 1 DESC LIMIT ?""", (months,)).fetchall()
    return [dict(r) for r in reversed(rows)]


class Budget(BaseModel):
    category: str
    month: str
    amount: float


@app.post("/api/budget")
def set_budget(b: Budget):
    """Applies from this month onward, until a later month overrides it."""
    cat = conn.execute("SELECT id FROM categories WHERE name=?", (b.category,)).fetchone()
    if not cat:
        raise HTTPException(404, "Unknown category")
    conn.execute("""INSERT INTO budgets(category_id, month, amount_cents) VALUES(?,?,?)
        ON CONFLICT(category_id, month) DO UPDATE SET amount_cents=excluded.amount_cents""",
                 (cat[0], b.month, round(b.amount * 100)))
    conn.commit()
    return {"ok": True}


from .connectors.plaid import Plaid  # noqa: E402


class Exchange(BaseModel):
    public_token: str
    institution: str | None = None


@app.get("/api/plaid/link-token")
def plaid_link_token():
    return {"link_token": Plaid(cfg["plaid"]).link_token()}


@app.post("/api/plaid/exchange")
def plaid_exchange(e: Exchange):
    Plaid(cfg["plaid"]).add_item(e.public_token, e.institution)
    return {"ok": True}


app.mount("/", StaticFiles(directory="web", html=True), name="web")
