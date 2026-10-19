import importlib
import time

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

PW = "correct horse battery"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("BUDGET_HOME", str(tmp_path))
    monkeypatch.setenv("TOKEN_KEY", Fernet.generate_key().decode())
    (tmp_path / "config.toml").write_text('[app]\ndb_path = "t.db"\n')
    from app import security
    return security


def _code(sec):
    return sec._totp(sec._read()["totp"], int(time.time() // 30))


def test_totp_matches_rfc6238_vector(env):
    assert env._totp("GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ", 59 // 30) == "287082"


def test_login_works_once_per_code(env):
    env.setup(PW)
    token, err = env.login(PW, _code(env))
    assert token and not err and env.valid_session(token)
    assert env.login(PW, _code(env))[0] is None  # replayed code is refused


def test_lockout_persists_and_blocks_good_login(env):
    env.setup(PW)
    for _ in range(5):
        assert env.login("wrong", "000000")[0] is None
    assert env._read()["locked_until"] > time.time()
    assert env.login(PW, _code(env))[1].startswith("Too many")


def test_idle_session_expires(env):
    env.setup(PW)
    token, _ = env.login(PW, _code(env))
    env._sessions[token]["seen"] -= env.SESSION_IDLE + 1
    assert not env.valid_session(token)


def test_tokens_are_encrypted_at_rest(env):
    from app.connectors import plaid
    plaid._save([{"item_id": "i", "access_token": "access-secret-123", "institution": "x", "cursor": ""}])
    assert b"access-secret-123" not in open(plaid._items_file(), "rb").read()
    assert plaid._load()[0]["access_token"] == "access-secret-123"


@pytest.fixture()
def client(env):
    from app import main
    importlib.reload(main)
    env.setup(PW)
    return TestClient(main.app, base_url="https://localhost", follow_redirects=False)


def test_requires_login(client):
    assert client.get("/api/summary").status_code == 401
    r = client.get("/")
    assert r.status_code == 307 and r.headers["location"].startswith("/login.html")


def test_wrong_host_rejected(client):
    assert client.get("/login.html", headers={"host": "evil.example"}).status_code == 400


def test_writes_need_header_and_same_origin(client, env):
    body = {"password": PW, "code": _code(env)}
    assert client.post("/api/login", json=body).status_code == 403
    assert client.post("/api/login", json=body, headers={"X-Budget": "1", "Origin": "https://evil.example"}).status_code == 403
    r = client.post("/api/login", json=body, headers={"X-Budget": "1"})
    assert r.status_code == 200 and "session" in r.cookies
    assert client.get("/api/summary").status_code == 200
    assert client.post("/api/sync").status_code == 403
    client.post("/api/logout", headers={"X-Budget": "1"})
    assert client.get("/api/summary").status_code == 401


def test_security_headers(client):
    h = client.get("/login.html").headers
    assert h["x-frame-options"] == "DENY" and "content-security-policy-report-only" in h


def test_missing_token_key_never_creates_a_new_one(env, monkeypatch):
    monkeypatch.setattr(env, "get_secret", lambda *a, **k: "")
    (env.home() / "plaid_items.enc").write_bytes(b"existing")
    with pytest.raises(RuntimeError):
        env.token_key()


def test_plaid_categories_map_and_user_rules_win(tmp_path):
    from app import db, rules
    conn = db.connect(str(tmp_path / "r.db"))
    name = lambda cid: conn.execute("SELECT name FROM categories WHERE id=?", (cid,)).fetchone()[0]
    pfc = {"personal_finance_category": {"primary": "FOOD_AND_DRINK", "detailed": "FOOD_AND_DRINK_GROCERIES"}}
    cat, transfer = rules.categorize(conn, "Trader Joe's", pfc)
    assert name(cat) == "Groceries" and transfer == 0
    assert rules.categorize(conn, "x", {"personal_finance_category": {"primary": "TRANSFER_OUT"}})[1] == 1
    conn.execute("INSERT INTO rules(pattern, category_id) VALUES('trader', (SELECT id FROM categories WHERE name='Dining'))")
    assert name(rules.categorize(conn, "Trader Joe's", pfc)[0]) == "Dining"


def test_backup_roundtrip_and_restore(env, tmp_path, monkeypatch):
    from app import backup, db
    monkeypatch.setenv("BACKUP_KEY", Fernet.generate_key().decode())
    db.connect(str(tmp_path / "t.db")).close()
    f = backup.create(tmp_path / "out")
    assert b"SQLite format" not in f.read_bytes()
    (tmp_path / "t.db").unlink()
    backup.restore(f)
    assert (tmp_path / "t.db").exists()


def test_posted_transaction_replaces_pending_twin(tmp_path):
    from app import db, sync
    from app.connectors.base import Connector, RawAccount, RawTxn

    class Fake(Connector):
        name = "fake"

        def __init__(self, txns):
            self.t = txns

        def fetch(self, since=None):
            return [RawAccount("a", "Checking")], self.t, []

    conn = db.connect(str(tmp_path / "s.db"))
    sync.run(conn, Fake([RawTxn("a", "p1", "2026-10-01", -100000, "Hub Cincinnati Nrent", True, {})]))
    sync.run(conn, Fake([RawTxn("a", "t1", "2026-10-02", -100000, "Hub Cincinnati NRent", False, {"pending_transaction_id": "p1"})]))
    assert conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 1


def test_rule_into_transfer_category_marks_transfer(tmp_path):
    from app import db, rules
    conn = db.connect(str(tmp_path / "x.db"))
    conn.execute("INSERT INTO rules(pattern, category_id) VALUES('zelle', (SELECT id FROM categories WHERE name='Transfer'))")
    assert rules.categorize(conn, "Zelle to Sam")[1] == 1


def test_drop_accounts_and_dedupe_pending(tmp_path):
    from app import db, items
    conn = db.connect(str(tmp_path / "i.db"))
    conn.execute("INSERT INTO accounts(id, provider, provider_account_id, name) VALUES(1,'plaid','a1','Checking'),(2,'plaid','a2','Checking')")
    for rid, acct, pend, day in ((1, 1, 1, "2026-10-01"), (2, 1, 0, "2026-10-02"), (3, 2, 0, "2026-10-02")):
        conn.execute("INSERT INTO raw_transactions(id, account_id, provider, provider_txn_id, posted_date, amount_cents, pending) VALUES(?,?,?,?,?,?,?)", (rid, acct, "plaid", f"t{rid}", day, -1000, pend))
        conn.execute("INSERT INTO transactions(raw_id, account_id, date, amount_cents, merchant) VALUES(?,?,?,?,?)", (rid, acct, day, -1000, "x"))
    assert items.dedupe_pending(conn) == 1
    assert items.drop_accounts(conn, ["a2"]) == 1
    assert conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 1
