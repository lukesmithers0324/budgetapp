# Budget dashboard (local)

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
