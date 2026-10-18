"""Delete this instance's data: python -m app.purge --yes
Revokes Plaid access for every saved connection, then removes the database, tokens, and login files.
Irreversible. (Plaid's Trial plan does not give the connection slot back.)"""
import sys

from . import security, sync
from .connectors import plaid

if __name__ == "__main__":
    if "--yes" not in sys.argv:
        sys.exit(__doc__)
    cfg = sync.load_config()
    client = plaid.Plaid(cfg.get("plaid", {}))
    for it in plaid._load():
        try:
            client._post("/item/remove", {"access_token": it["access_token"]})
        except Exception as e:
            print("could not revoke one connection:", e)
    home = security.home()
    for name in (cfg["app"]["db_path"], "plaid_items.enc", "auth.json"):
        (home / name).unlink(missing_ok=True)
    print("purged", home)
