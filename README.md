# Budget dashboard

A personal budgeting dashboard that runs on my own computer. It pulls my own bank transactions through Plaid Link (the Transactions product only), stores them in a local SQLite file, and shows spending, budgets, and trends on a localhost web page.

- **Who uses it:** one person, for their own accounts. It is not a public service and has no other users.
- **What it asks Plaid for:** transaction data only. It never moves money.
- **Where data lives:** on the local machine only. Plaid access tokens are kept in a local file with owner-only permissions. Nothing is sent to analytics or to any third party other than Plaid.
- **Secrets:** API keys and tokens are kept out of this repository (see `.gitignore`).
- **Built with:** Python, FastAPI, SQLite, and plain HTML/JS. See `PLAN.md` for the design.

## Setup

Python 3.11+. Runs on your machine only (127.0.0.1). See PLAN.md for the design.

```
python3 -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp config.example.toml config.toml && chmod 600 config.toml

# one-time: exchange your SimpleFIN setup token for the access URL, paste it into config.toml
python -c "from app.connectors.simplefin import claim; print(claim(input('setup token: ')))"

uvicorn app.main:app --host 127.0.0.1 --port 8000   # open http://127.0.0.1:8000
python -m app.sync                                  # manual or scheduled sync
```

Opening the dashboard syncs automatically if the last sync is over 12 hours old.
The access URL is a secret: keep it only in config.toml, never in chat, issues, or logs.

## Plaid setup (free Trial plan)
1. Create a Plaid account, copy your client_id and production secret into the `[plaid]` section of config.toml.
2. In the Plaid dashboard, add `https://localhost:8000/` under allowed redirect URIs (it must match config.toml exactly).
3. Local HTTPS (needed for bank-login redirects): `brew install mkcert && mkcert -install && mkcert localhost`
4. Run: `uvicorn app.main:app --host 127.0.0.1 --port 8000 --ssl-keyfile localhost-key.pem --ssl-certfile localhost.pem`
5. Open https://localhost:8000 and click **Connect a bank**. Access tokens are saved in `plaid_items.json` (chmod 600, never share it).
The Trial plan allows 10 connections and removing one does not free its slot, so avoid reconnecting the same bank repeatedly.

## Security notes
- Set the login passphrase once: `python -m app.security` (username `budget`, 12+ characters). Without it every request is refused.
- Plaid keys: put them in the environment (`PLAID_CLIENT_ID`, `PLAID_SECRET`) or the OS keychain (service `budget`) instead of config.toml. Config values are only a fallback.
- Access tokens are encrypted at rest (`plaid_items.enc`); the key is created in the OS keychain.
- The server only answers to the host name `localhost` over HTTPS and locks out repeated bad logins.
- The SQLite database is not encrypted by the app. Keep full-disk encryption (FileVault) on.
- Check dependencies with `pip-audit -r requirements.txt`; Dependabot is configured for the public repo.
