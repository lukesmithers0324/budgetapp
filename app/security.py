"""Local-app hardening: passphrase gate with lockout, secrets from env/keychain, token key."""
import base64
import getpass
import hashlib
import hmac
import json
import os
import sys
import time

AUTH_FILE = "auth.json"  # scrypt hash + salt only (chmod 600, gitignored)
_fails = {}  # client -> (failure count, locked until)
_good = set()  # sha256 of Authorization headers already verified this process


def _scrypt(pw, salt):
    return hashlib.scrypt(pw.encode(), salt=salt, n=2**15, r=8, p=1, maxmem=2**26, dklen=32)


def set_passphrase(pw):
    salt = os.urandom(16)
    fd = os.open(AUTH_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"salt": salt.hex(), "hash": _scrypt(pw, salt).hex()}, f)


def check_passphrase(pw):
    try:
        with open(AUTH_FILE) as f:
            d = json.load(f)
    except FileNotFoundError:
        return False  # fail closed until a passphrase is set
    return hmac.compare_digest(_scrypt(pw, bytes.fromhex(d["salt"])).hex(), d["hash"])


def verify_header(auth):
    h = hashlib.sha256(auth.encode()).hexdigest()
    if h in _good:
        return True
    try:
        user, _, pw = base64.b64decode(auth[6:]).decode().partition(":")
    except Exception:
        return False
    ok = user == "budget" and check_passphrase(pw)
    if ok:
        _good.add(h)
    return ok


def locked(client):
    return _fails.get(client, (0, 0))[1] > time.time()


def record(client, ok):
    if ok:
        _fails.pop(client, None)
        return
    n = _fails.get(client, (0, 0))[0] + 1
    _fails[client] = (n, time.time() + min(900, 2 ** n) if n >= 5 else 0)


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
    except Exception:
        pass
    return fallback


def token_key():
    """Encryption key for stored access tokens. Created once and kept in the OS keychain."""
    k = get_secret("TOKEN_KEY")
    if not k:
        import keyring
        k = base64.urlsafe_b64encode(os.urandom(32)).decode()
        keyring.set_password("budget", "TOKEN_KEY", k)
    return k


if __name__ == "__main__":
    a, b = getpass.getpass("New passphrase: "), getpass.getpass("Repeat: ")
    if a != b or len(a) < 12:
        sys.exit("Passphrases must match and be at least 12 characters.")
    set_passphrase(a)
    print("Saved. The login username is 'budget'.")
