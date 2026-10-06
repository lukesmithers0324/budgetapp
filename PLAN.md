# Budget dashboard: plan

## Decisions so far
- Personal finances, run locally on your own computer (localhost only).
- Automatic bank sync is required. First connector: Plaid's free Trial plan (US/Canada, 10-connection cap; bank logins need https://localhost via mkcert). SimpleFIN Bridge (about $15/yr) is built as a second connector; CSV import per account is still planned.
- Stack: Python, FastAPI, SQLite, static HTML/JS (no build step).

## Questions it answers
1. Where did my money go this month?
2. Am I on track against my budget, by category?
3. Is income minus spending trending the right way?

## Architecture
- Server binds to 127.0.0.1. Secrets live only in config.toml (gitignored, chmod 600), never in the DB or logs.
- Sync runs when the dashboard opens if the last sync is over 12h old (`POST /api/sync`), or on demand/schedule with `python -m app.sync`.
- Layers: `raw_transactions` (provider data, never edited) then `transactions` (normalized, with your edits). Re-syncs never overwrite edited fields.
- Money is stored as integer cents. Back up the SQLite file daily; encrypt it if the folder syncs to a cloud drive.

## Sync algorithm
1. Request transactions from (last good sync minus 7 days).
2. Upsert raw rows by (provider, provider txn ID). CSV rows get a deterministic ID from account, date, amount, description, and occurrence number.
3. Create a normalized transaction for each new raw row and apply rules, skipping hand-edited fields.
4. Reconcile pending to posted when a provider changes IDs.
5. Suggest transfers by pairing equal and opposite amounts across accounts; confirm before excluding.
6. Log every run in `sync_runs` and show errors on the dashboard.

## Rules
Ordered, first match wins, matching merchant text. Recategorizing offers to create a rule with a preview of affected transactions. Manual edits always win.

## Build phases
- **Phase 0 (you):** sign up for SimpleFIN and link accounts; check each shows recent transactions and note how far back history goes; export bank CSVs (share only headers plus a few redacted rows); decide categories and budget style; confirm Python 3.11+.
- **Phase 1:** sync plus CSV backfill, categories and rules, transactions table, month overview with budget vs actual.
- **Phase 2:** trends, review queue, recurring-charge detection, backups, second connector.
- **Phase 3:** alerts, goals, net worth, phone-friendly layout.

## Phase 1 is done when
- Running sync twice adds nothing new.
- A category you changed survives a re-sync.
- Importing the same CSV twice changes nothing.
- One real month's totals match your bank statements.
- The dashboard shows budget vs actual for that month.

## Open (defaults in place)
Budget style (monthly cap per category), month start day (the 1st), category list.

## Security
Never paste the SimpleFIN access URL or tokens into chat, issues, or logs.

## Skeleton status
Built: schema, SimpleFIN connector (first draft, verify against its developer guide), sync, basic rules, API, dashboard with percent rings, charts, filterable transactions, and per-category budgets.
Not yet built: CSV import, pending-to-posted reconcile, transfer detection, rules UI, backups, tests.
