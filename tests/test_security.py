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
