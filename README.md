# Budget dashboard

A small budgeting dashboard for me and my partner. Each person runs their own isolated instance, with their own login, database, and bank connections. Bank data comes through Plaid Link (Transactions product only), is stored in a local SQLite file, and is shown on a private web page.

- **Who uses it:** two people who know each other, each connecting only their own accounts through Plaid Link. It is not a public service.
- **What it asks Plaid for:** transaction data only. It never moves money and never sees bank credentials.
- **Where data lives:** on the machine running that person's instance, in a per-person data folder. Plaid access tokens are encrypted at rest. Nothing is sent to analytics or to any third party other than Plaid.
- **Secrets:** API keys and tokens stay out of this repository (see `.gitignore`).
- **Built with:** Python, FastAPI, SQLite, and plain HTML/JS. See `PLAN.md` for the design and `docs/DEPLOY.md` for hosting.

## Setup

Python 3.11 or newer.

```
python3 -m venv .venv
. .venv/bin/activate
pip install --require-hashes -r requirements.txt
cp config.example.toml config.toml
chmod 600 config.toml
python -m app.security
```

`python -m app.security` sets a passphrase (12+ characters) and prints a key for an authenticator app. Every login needs the passphrase plus the 6-digit code, and without it every request is refused.

## Plaid (free Trial plan)

1. Create a Plaid account and copy your client ID and production secret.
2. Store them in the OS keychain (or the `PLAID_CLIENT_ID` and `PLAID_SECRET` environment variables), not in config.toml:

```
python -c "import keyring, getpass; keyring.set_password('budget', 'PLAID_CLIENT_ID', getpass.getpass('Plaid client id: '))"
python -c "import keyring, getpass; keyring.set_password('budget', 'PLAID_SECRET', getpass.getpass('Plaid production secret: '))"
```

3. In the Plaid dashboard, add `https://localhost:8000/` under allowed redirect URIs. It must match `redirect_uri` in config.toml exactly.
4. Make a local HTTPS certificate (needed for bank-login redirects):

```
brew install mkcert
mkcert -install
mkcert localhost
```

5. Run the server and open https://localhost:8000:

```
uvicorn app.main:app --host 127.0.0.1 --port 8000 --ssl-keyfile localhost-key.pem --ssl-certfile localhost.pem
```

Click **Connect a bank** once per bank. The Trial plan allows 10 connections in total, and removing one does not give the slot back. Restarting the server and **Sync now** reuse the saved tokens and do not create connections.

## Security notes

- Plaid access tokens are stored encrypted in `plaid_items.enc`. The key lives in the OS keychain or the `TOKEN_KEY` environment variable, and the app refuses to create a new key while encrypted tokens exist.
- The app answers only to the hosts listed in `allowed_hosts` (default `localhost`), uses session cookies, checks the Origin and an `X-Budget` header on every write, and locks out repeated bad logins.
- The SQLite database is not encrypted by the app, so run it on an encrypted disk.
- A Content-Security-Policy is sent in report-only mode. After checking that Plaid Link works with no policy errors in the browser console, set `csp = "enforce"` under `[app]` in config.toml.
- To run several independent instances, give each its own `BUDGET_HOME` folder, port, passphrase, and token key.
- Encrypted backups: `python -m app.backup DEST_DIR` (needs `BACKUP_KEY`). Remove an instance's data: `python -m app.purge --yes`.

## Optional: SimpleFIN connector

If `access_url` is set in the `[simplefin]` section of config.toml, SimpleFIN transactions are synced too.

## Tests and dependencies

- Run the tests from the project folder: `python -m pytest -q` (install `pytest` first).
- Pin dependencies with hashes: `pip install pip-tools`, then `pip-compile --generate-hashes requirements.in -o requirements.txt`.
- Check for known vulnerabilities with `pip-audit -r requirements.txt`. Dependabot is configured for this repo.
