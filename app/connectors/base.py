from dataclasses import dataclass


@dataclass
class RawAccount:
    provider_account_id: str
    name: str
    institution: str = ""


@dataclass
class RawTxn:
    provider_account_id: str
    provider_txn_id: str
    date: str  # YYYY-MM-DD
    amount_cents: int  # negative = money out
    description: str
    pending: bool = False
    payload: dict | None = None


class Connector:
    """Every source (SimpleFIN, CSV, Plaid later) returns this same shape."""
    name = "base"

    def fetch(self, since: str | None) -> tuple[list[RawAccount], list[RawTxn], list]:
        raise NotImplementedError
