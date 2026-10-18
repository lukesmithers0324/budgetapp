# Hosting for two people (Linux host + Tailscale)

One instance per person: separate OS user, data folder, database, encrypted tokens, login, and port. The host admin can still read everyone's data, so tell the other person before you start. Verify commands against current docs for your distro and Tailscale before relying on them.

## 1. Prepare the host
- Ubuntu Server LTS on a machine or VM you control, installed with full-disk encryption (LUKS).
- Automatic security updates on. Firewall default-deny for incoming traffic. SSH key-only, or no SSH at all.
- No router port forwarding. Nothing is exposed to the internet.

## 2. Tailscale
- Install Tailscale and sign in, enable MagicDNS and HTTPS certificates in the admin console, then run `tailscale up`.
- Note the host's name, like `host.your-tailnet.ts.net`.

## 3. Install the app
```
sudo mkdir -p /opt/budget /etc/budget /srv/budget
sudo cp -r app web requirements.txt /opt/budget/
cd /opt/budget && sudo python3 -m venv .venv
sudo .venv/bin/pip install --require-hashes -r requirements.txt
sudo cp deploy/budget@.service /etc/systemd/system/
```

## 4. Create one instance per person (repeat with a new NAME and PORT)
```
sudo useradd --system --home /srv/budget/NAME --shell /usr/sbin/nologin budget-NAME
sudo install -d -m 700 -o budget-NAME /srv/budget/NAME
sudo install -m 600 /dev/null /etc/budget/NAME.env
```
Edit `/etc/budget/NAME.env` (root-owned, mode 600) with `PORT=8001`, `PLAID_CLIENT_ID`, `PLAID_SECRET`, `TOKEN_KEY`, and `BACKUP_KEY`. Generate each key with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` and keep copies in a password manager, separate from backups.

Create `/srv/budget/NAME/config.toml`:
```
[app]
db_path = "budget.db"
allowed_hosts = ["localhost", "host.your-tailnet.ts.net"]
[plaid]
env = "production"
redirect_uri = "https://host.your-tailnet.ts.net/"
user_id = "NAME"
```
Set the login as that user, with the person present to type their own passphrase and scan the setup key:
```
sudo -u budget-NAME env BUDGET_HOME=/srv/budget/NAME /opt/budget/.venv/bin/python -m app.security
sudo systemctl enable --now budget@NAME
```

## 5. Publish over private HTTPS
Tailscale serve proxies a tailnet HTTPS port to the local port. Use a different HTTPS port per person:
```
tailscale serve --bg --https=443 localhost:8001
tailscale serve --bg --https=8443 localhost:8002
```
The second person's address is `https://host.your-tailnet.ts.net:8443/`, so that exact URL goes in their `redirect_uri` and `allowed_hosts`.

## 6. Plaid
- Add each instance's HTTPS address to Plaid's allowed redirect URIs (exact match, trailing slash included).
- All connections count toward the same Trial limit of 10, and removing one does not give the slot back.
- Each person connects their own bank through Link. You never see their bank login.

## 7. Onboarding the second person
- She installs Tailscale and gets access to the host (invite her or share the node), then restrict her with an access rule to only her HTTPS port. Check Tailscale's current ACL syntax and plan limits.
- She uses her own passphrase and authenticator app, and connects her own bank.

## 8. Backups
Run daily from a systemd timer or cron as that user, writing to a folder on a different disk:
```
sudo -u budget-NAME env BUDGET_HOME=/srv/budget/NAME /opt/budget/.venv/bin/python -m app.backup /srv/backups/NAME
```
Backups hold the database and encrypted tokens but not the login file. Keep `TOKEN_KEY` and `BACKUP_KEY` somewhere else. Test a restore (`python -m app.backup --restore FILE`, with the service stopped) every few months.

## 9. Maintenance and offboarding
- Monthly: update the OS, run `pip-audit`, review who has Tailscale access.
- To remove a person: `sudo -u budget-NAME env BUDGET_HOME=/srv/budget/NAME /opt/budget/.venv/bin/python -m app.purge --yes`, then disable the service and delete the user.
