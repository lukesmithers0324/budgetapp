"""Local-app hardening: login (passphrase + TOTP), sessions, persistent lockout, secrets, token key."""
import base64
import getpass
import hashlib
import hmac
import json
import os
import secrets
import struct
import sys
import time
from pathlib import Path

SESSION_IDLE, SESSION_MAX = 30 * 60, 12 * 3600
_sessions = {}  # token -> {"created": t, "seen": t}


def home():
    """Per-instance data folder (mode 0700). Set BUDGET_HOME to run independent instances side by side."""
    p = Path(os.environ.get("BUDGET_HOME", "."))
    p.mkdir(mode=0o700, parents=True, exist_ok=True)
    return p


def _auth_path():
    return home() / "auth.json"


def _read():
    try:
        return json.loads(_auth_path().read_text())
    except FileNotFoundError:
        return None


def _write(d):
    fd = os.open(_auth_path(), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(d, f)


def _scrypt(pw, salt):
    return hashlib.scrypt(pw.encode(), salt=salt, n=2**15, r=8, p=1, maxmem=2**26, dklen=32)


def _totp(secret_b32, step):
    mac = hmac.new(base64.b32decode(secret_b32), struct.pack(">Q", step), hashlib.sha1).digest()
    o = mac[-1] & 15
    return f"{(struct.unpack('>I', mac[o:o + 4])[0] & 0x7FFFFFFF) % 10**6:06d}"


def setup(pw):
    salt, secret = os.urandom(16), base64.b32encode(os.urandom(20)).decode()
    _write({"salt": salt.hex(), "hash": _scrypt(pw, salt).hex(), "totp": secret,
            "last_step": 0, "fails": 0, "locked_until": 0})
    return secret


def login(pw, code):
    """Returns (session_token, None) or (None, message). Failure counts persist across restarts."""
    d = _read()
    if d is None:
        return None, "Run python -m app.security first."
    now = time.time()
    if d["locked_until"] > now:
        return None, "Too many attempts. Try again later."
    step = int(now // 30)
    ok_pw = hmac.compare_digest(_scrypt(pw, bytes.fromhex(d["salt"])).hex(), d["hash"])
    used = next((s for s in (step - 1, step, step + 1)
                 if s > d["last_step"] and hmac.compare_digest(_totp(d["totp"], s), code)), None)
    if ok_pw and used:
        d.update(fails=0, locked_until=0, last_step=used)  # last_step blocks code replay
        _write(d)
        token = secrets.token_urlsafe(32)
        _sessions[token] = {"created": now, "seen": now}
        return token, None
    d["fails"] += 1
    if d["fails"] >= 5:
        d["locked_until"] = now + min(3600, 2 ** d["fails"])
    _write(d)
    return None, "Invalid credentials."


def valid_session(token):
    s, now = _sessions.get(token or ""), time.time()
    if not s or now - s["seen"] > SESSION_IDLE or now - s["created"] > SESSION_MAX:
        _sessions.pop(token or "", None)
        return False
    s["seen"] = now
    return True


def logout(token):
    _sessions.pop(token or "", None)


def get_secret(name, fallback=""):
    """Order: environment variable, OS keychain (service 'budget'), then the config value."""
    v = os.environ.get(name)
    if v:
        return v
    try:
        import keyring
        v = keyring.get_password("budget", name)
        if v:
            return v
    except Exception as e:  # keyring missing or locked: say so (never the value) and fall back
        print(f"warning: keychain lookup for {name} failed ({type(e).__name__}); using fallback", file=sys.stderr)
    return fallback


def token_key():
    """Encryption key for stored access tokens. Created once and kept in the OS keychain (or TOKEN_KEY env)."""
    k = get_secret("TOKEN_KEY")
    if not k:
        if (home() / "plaid_items.enc").exists():  # never replace a key that may still decrypt saved tokens
            raise RuntimeError("TOKEN_KEY not found but encrypted tokens exist; refusing to create a new key")
        import keyring
        k = base64.urlsafe_b64encode(os.urandom(32)).decode()
        keyring.set_password("budget", "TOKEN_KEY", k)
    return k


if __name__ == "__main__":
    a, b = getpass.getpass("New passphrase: "), getpass.getpass("Repeat: ")
    if a != b or len(a) < 12:
        sys.exit("Passphrases must match and be at least 12 characters.")
    s = setup(a)
    print(f"Saved to {_auth_path()}.\nAdd this key to an authenticator app (setup key, time-based):\n  {s}")
    print(f"or open: otpauth://totp/Budget?secret={s}&issuer=Budget")
