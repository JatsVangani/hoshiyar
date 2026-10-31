# Deploying Hoshiyar on the VPS

Ubuntu 24.04, 1 CPU, 1 GB RAM, an LXC container on AIC Cloud, root over SSH on port 20065. The container does
not own a public address: the provider forwards its HTTPS URL (https://ow2xj.aiccloud.online) and a direct port
(http://148.113.17.68:40065) to the container's port 80 and terminates TLS itself. Caddy therefore serves plain
HTTP on 80 and forwards to the app. The public URL is the provider's; a custom domain needs a Cloudflare Tunnel
on the box (outbound, no ports), not an A record. The repo is copied with rsync, not git.

## First deploy

```sh
# 1. Copy the repo (without the venv, data and scratch), then the two files git never carries, and point
#    the box's copy of .env at its own hostname. The laptop's .env keeps its ngrok URL.
rsync -avz -e "ssh -p 20065" --exclude .venv --exclude .git --exclude scratch --exclude data --exclude .env --exclude __pycache__ \
      ./ root@148.113.17.68:/opt/hoshiyar/
scp -P 20065 .env root@148.113.17.68:/opt/hoshiyar/.env
ssh -p 20065 root@148.113.17.68 "sed -i 's#^LOCAL_SERVER_URL=.*#LOCAL_SERVER_URL=https://ow2xj.aiccloud.online#' /opt/hoshiyar/.env && mkdir -p /opt/hoshiyar/data"
scp -P 20065 data/drivers.json root@148.113.17.68:/opt/hoshiyar/data/drivers.json

# 2. On the box: swap, timezone, packages, uv, venv, service, Caddy. About five minutes.
ssh -p 20065 root@148.113.17.68 "bash /opt/hoshiyar/deploy/vps-setup.sh"
```

Then open https://ow2xj.aiccloud.online/fleet, book a trial, and watch the logs while the phone rings:

```sh
ssh -p 20065 root@148.113.17.68 "journalctl -u hoshiyar -f"
```

## Updating after a change

```sh
rsync -avz -e "ssh -p 20065" --exclude .venv --exclude .git --exclude scratch --exclude data --exclude .env --exclude __pycache__ \
      ./ root@148.113.17.68:/opt/hoshiyar/
ssh -p 20065 root@148.113.17.68 "systemctl restart hoshiyar"
```

If `pyproject.toml` or `uv.lock` changed, run `cd /opt/hoshiyar && uv sync --frozen --no-dev` on the box before the restart.

## Day to day

```sh
ssh -p 20065 root@148.113.17.68
systemctl status hoshiyar        # running? restarts?
journalctl -u hoshiyar -f        # live log, the same lines the laptop terminal showed
journalctl -u hoshiyar --since "1 hour ago"
systemctl restart hoshiyar
vi /opt/hoshiyar/data/drivers.json   # the rota re-reads it every 20 s, no restart needed
free -m                          # memory; swap in use is fine, swap exhausted is not
```

## What to know

- One process only. The scheduler's calls and the alert queue are in memory.
- This VPS is an LXC container (kernel `pve`): swap cannot be enabled, so the 1 GB is all there is. The app idles
  near 250 MB and a call adds about 100; the unit restarts it within 3 s if it is ever killed. Watch `free -m`.
- `TZ=Asia/Kolkata` is set in the unit. The roster's check-in times are local time.
- `data/` on the box holds the roster, records, schedule and trials. It is never overwritten by the rsync above.
- `.env` lives only on the laptop and the box. Never commit it, never paste it anywhere.
- Ports: the provider forwards 20065 to SSH and its web URLs to port 80 (Caddy). The app listens on 127.0.0.1:7860
  (the unit sets HOST), so only Caddy reaches it; on the laptop HOST is unset and it binds 0.0.0.0 for ngrok.
- Let's Encrypt cannot issue to this box (ports 80/443 on the shared address are the provider's), so never turn
  Caddy's automatic HTTPS back on here.
