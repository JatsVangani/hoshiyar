#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu 24.04 VPS for Hoshiyar. Run as root from inside /opt/hoshiyar after the
# repo has been copied there (see deploy.md). Safe to re-run.
set -euo pipefail
cd /opt/hoshiyar

echo "== swap (1 GB) =="
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "== timezone =="
timedatectl set-timezone Asia/Kolkata

echo "== packages =="
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q curl ca-certificates build-essential portaudio19-dev debian-keyring debian-archive-keyring apt-transport-https gnupg
if ! command -v caddy >/dev/null; then
  curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -q && apt-get install -y -q caddy
fi

echo "== uv =="
if [ ! -x /root/.local/bin/uv ]; then curl -LsSf https://astral.sh/uv/install.sh | sh; fi
export PATH=/root/.local/bin:$PATH

echo "== python environment =="
rm -rf .venv
uv sync --frozen --no-dev

echo "== service and caddy =="
mkdir -p data
cp deploy/hoshiyar.service /etc/systemd/system/hoshiyar.service
cp deploy/Caddyfile /etc/caddy/Caddyfile
systemctl daemon-reload
systemctl enable --now hoshiyar
systemctl restart caddy

echo "== firewall =="
if command -v ufw >/dev/null; then ufw allow 20065/tcp >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null; fi

sleep 3
systemctl --no-pager --lines=5 status hoshiyar || true
echo
echo "Done. Check: curl -s http://127.0.0.1:7860/fleet | head -c 200"
