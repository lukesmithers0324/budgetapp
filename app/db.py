import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts(
  id INTEGER PRIMARY KEY, provider TEXT NOT NULL, provider_account_id TEXT NOT NULL,
  name TEXT, institution TEXT, type TEXT, active INTEGER DEFAULT 1, last_synced_at TEXT,
  UNIQUE(provider, provider_account_id));
CREATE TABLE IF NOT EXISTS raw_transactions(
  id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES accounts(id),
  provider TEXT NOT NULL, provider_txn_id TEXT NOT NULL, posted_date TEXT,
  amount_cents INTEGER NOT NULL, description TEXT, pending INTEGER DEFAULT 0, payload TEXT,
  first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(provider, provider_txn_id));
CREATE TABLE IF NOT EXISTS categories(
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('income','expense','transfer')),
  parent_id INTEGER REFERENCES categories(id));
CREATE TABLE IF NOT EXISTS transactions(
  id INTEGER PRIMARY KEY, raw_id INTEGER UNIQUE REFERENCES raw_transactions(id),
  account_id INTEGER NOT NULL REFERENCES accounts(id), date TEXT NOT NULL,
  amount_cents INTEGER NOT NULL, merchant TEXT, category_id INTEGER REFERENCES categories(id),
  is_transfer INTEGER DEFAULT 0, notes TEXT, edited_fields TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS budgets(
  id INTEGER PRIMARY KEY, category_id INTEGER NOT NULL REFERENCES categories(id),
  month TEXT NOT NULL, amount_cents INTEGER NOT NULL, UNIQUE(category_id, month));
CREATE TABLE IF NOT EXISTS rules(
  id INTEGER PRIMARY KEY, priority INTEGER NOT NULL DEFAULT 100, pattern TEXT NOT NULL,
  category_id INTEGER NOT NULL REFERENCES categories(id));
CREATE TABLE IF NOT EXISTS sync_runs(
  id INTEGER PRIMARY KEY, connector TEXT, started_at TEXT, finished_at TEXT,
  status TEXT, new_rows INTEGER DEFAULT 0, error TEXT);
"""

DEFAULT_CATEGORIES = [
    ("Income", "income"), ("Transfer", "transfer"), ("Housing", "expense"),
    ("Groceries", "expense"), ("Dining", "expense"), ("Transport", "expense"),
    ("Utilities", "expense"), ("Shopping", "expense"), ("Health", "expense"),
    ("Entertainment", "expense"), ("Travel", "expense"), ("Other", "expense"),
]


def connect(path):
    conn = sqlite3.connect(path, check_same_thread=False)  # single local user
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    conn.executemany("INSERT OR IGNORE INTO categories(name, kind) VALUES(?,?)", DEFAULT_CATEGORIES)
    conn.commit()
    return conn
