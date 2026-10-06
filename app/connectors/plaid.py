# First draft: verify request/response fields against Plaid's docs before relying on it.
import json
import os
from decimal import Decimal

import httpx

from .base import Connector, RawAccount, RawTxn

HOSTS = {"production": "https://production.plaid.com", "sandbox": "https://sandbox.plaid.com"}
ITEMS_FILE = "plaid_items.json"  # holds access tokens: chmod 600, gitignored, never share


def _load():
    try:
        with open(ITEMS_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def _save(items):
    fd = os.open(ITEMS_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(items, f)


def has_items():
    return bool(_load())


class Plaid(Connector):
    name = "plaid"

    def __init__(self, cfg):
        self.cfg = cfg
        self.base = HOSTS[cfg.get("env", "production")]
        self.removed, self._cursors = [], {}

    def _post(self, path, body):
        r = httpx.post(self.base + path, timeout=60,
                       json={"client_id": self.cfg["client_id"], "secret": self.cfg["secret"], **body})
        if r.status_code >= 400:
            try:
                code = r.json().get("error_code")
            except ValueError:
                code = None
            raise RuntimeError(f"Plaid {path} failed: {code or r.status_code}")
        return r.json()

    def link_token(self):
        body = {"client_name": "Budget", "language": "en", "country_codes": ["US"],
                "products": ["transactions"], "user": {"client_user_id": "local-user"}}
        if self.cfg.get("redirect_uri"):
            body["redirect_uri"] = self.cfg["redirect_uri"]
        return self._post("/link/token/create", body)["link_token"]

    def add_item(self, public_token, institution):
        d = self._post("/item/public_token/exchange", {"public_token": public_token})
        items = _load()
        items.append({"item_id": d["item_id"], "access_token": d["access_token"],
                      "institution": institution or "", "cursor": ""})
        _save(items)

    def fetch(self, since=None):
        accounts, txns, self.removed, self._cursors = [], [], [], {}
        for it in _load():
            cur = it.get("cursor", "")
            while True:
                d = self._post("/transactions/sync", {"access_token": it["access_token"], "cursor": cur, "count": 500})
                for a in d.get("accounts", []):
                    accounts.append(RawAccount(a["account_id"], a.get("name", ""), it["institution"]))
                for t in d["added"] + d["modified"]:
                    cents = -int(round(Decimal(str(t["amount"])) * 100))  # Plaid: positive = money out
                    txns.append(RawTxn(t["account_id"], t["transaction_id"], t["date"], cents,
                                       t.get("merchant_name") or t.get("name", ""), bool(t.get("pending")), t))
                self.removed += [x["transaction_id"] for x in d["removed"]]
                cur = d["next_cursor"]
                if not d["has_more"]:
                    break
            self._cursors[it["item_id"]] = cur
        return accounts, txns, []

    def commit(self):
        """Called after the DB commit, so a failed sync never loses a cursor position."""
        items = _load()
        for it in items:
            it["cursor"] = self._cursors.get(it["item_id"], it.get("cursor", ""))
        _save(items)
