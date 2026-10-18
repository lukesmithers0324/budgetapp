"""Encrypted backups.  Create: python -m app.backup DEST_DIR   Restore: python -m app.backup --restore FILE
Needs BACKUP_KEY (env or keychain): a Fernet key kept apart from TOKEN_KEY. Stop the app before restoring."""
import io
import sqlite3
import sys
import tarfile
import time
from pathlib import Path

from cryptography.fernet import Fernet

from . import security, sync

KEEP = 14


def _fernet():
    k = security.get_secret("BACKUP_KEY")
    if not k:
        sys.exit("BACKUP_KEY is not set. Generate one with Fernet.generate_key() and keep it in your password manager.")
    return Fernet(k.encode())


def create(dest):
    home, cfg = security.home(), sync.load_config()
    name = Path(cfg["app"]["db_path"]).name
    snap = home / "snapshot.tmp"
    src, dst = sqlite3.connect(home / name), sqlite3.connect(snap)
    src.backup(dst)
    dst.close()
    src.close()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:  # login file is left out on purpose
        tar.add(snap, arcname=name)
        if (home / "plaid_items.enc").exists():
            tar.add(home / "plaid_items.enc", arcname="plaid_items.enc")
    snap.unlink()
    out = Path(dest)
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    f = out / time.strftime("budget-%Y%m%d-%H%M%S.enc")
    f.write_bytes(_fernet().encrypt(buf.getvalue()))
    f.chmod(0o600)
    for old in sorted(out.glob("budget-*.enc"))[:-KEEP]:
        old.unlink()
    return f


def restore(file):
    data = _fernet().decrypt(Path(file).read_bytes())
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for m in tar.getmembers():
            if not m.isfile() or m.name != Path(m.name).name:
                sys.exit("unexpected entry in backup")
            tar.extract(m, security.home(), filter="data")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--restore":
        restore(sys.argv[2])
        print("restored")
    elif len(sys.argv) == 2:
        print("wrote", create(sys.argv[1]))
    else:
        sys.exit(__doc__)
