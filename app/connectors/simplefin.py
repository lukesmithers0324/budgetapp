# First draft: verify endpoints and fields against SimpleFIN's developer guide before relying on it.
import base64
import datetime as dt
from decimal import Decimal

import httpx

from .base import Connector, RawAccount, RawTxn


def claim(setup_token: str) -> str:
    """One-time: exchange a setup token for the access URL (the secret that goes in config.toml)."""
    claim_url = base64.b64decode(setup_token.strip()).decode()
    r = httpx.post(claim_url)
    r.raise_for_status()
    return r.text.strip()


class SimpleFIN(Connector):
    name = "simplefin"

    def __init__(self, access_url: str):
        self.access_url = access_url.rstrip("/")

    def fetch(self, since=None):
        params = {"pending": 1}
        if since:
            params["start-date"] = int(dt.datetime.fromisoformat(since).timestamp())
        r = httpx.get(self.access_url + "/accounts", params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        accounts, txns = [], []
        for a in data.get("accounts", []):
            accounts.append(RawAccount(a["id"], a.get("name", ""), (a.get("org") or {}).get("name", "")))
            for t in a.get("transactions", []):
                ts = t.get("posted") or 0
                day = (dt.datetime.fromtimestamp(ts, dt.timezone.utc).date() if ts else dt.date.today()).isoformat()
                txns.append(RawTxn(a["id"], t["id"], day, int(Decimal(t["amount"]) * 100),
                                   t.get("description", ""), not ts or bool(t.get("pending")), t))
        return accounts, txns, data.get("errors", [])
