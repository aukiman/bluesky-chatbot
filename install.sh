#!/usr/bin/env bash
set -euo pipefail

# --- Config ---
REPO="aukiman/bluesky-chatbot"
TAR_NAME="${TAR_NAME:-bsky-bots-v3.tar.gz}"
BRANCH="${BRANCH:-main}"
RAW_BASE="https://raw.githubusercontent.com/${REPO}/${BRANCH}"
TAR_URL="${TAR_URL:-${RAW_BASE}/${TAR_NAME}}"

# --- Must be root ---
if [[ $EUID -ne 0 ]]; then
  echo "Please run as root, e.g.: sudo bash install.sh"
  exit 1
fi

echo "[*] Installing system dependencies..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  python3 python3-venv python3-pip python3-dev \
  git curl ca-certificates \
  build-essential pkg-config \
  sqlite3

# --- User + dirs ---
id -u bskybots &>/dev/null || useradd --system --home /opt/bsky-bots --shell /usr/sbin/nologin bskybots
install -d -o bskybots -g bskybots -m 0755 /opt/bsky-bots
install -d -o bskybots -g bskybots -m 0755 /var/lib/bsky-bots
install -d -o bskybots -g bskybots -m 0755 /var/log/bsky-bots
install -d -o root     -g bskybots -m 0750 /etc/bsky-bots

# --- Fetch tarball ---
echo "[*] Downloading ${TAR_URL}"
tmpdir="$(mktemp -d)"
curl -fsSL "${TAR_URL}" -o "${tmpdir}/${TAR_NAME}"

echo "[*] Unpacking..."
tar -xzf "${tmpdir}/${TAR_NAME}" -C "${tmpdir}"

# app/
rsync -a "${tmpdir}/app/" /opt/bsky-bots/ --exclude '__pycache__' --exclude '*.pyc'
chown -R bskybots:bskybots /opt/bsky-bots

# venv + python deps
echo "[*] Creating venv + installing requirements..."
sudo -u bskybots python3 -m venv /opt/bsky-bots/.venv
sudo -u bskybots /opt/bsky-bots/.venv/bin/pip install --upgrade pip wheel
sudo -u bskybots /opt/bsky-bots/.venv/bin/pip install -r /opt/bsky-bots/requirements.txt

# configs (do not overwrite if already exist)
[[ -f /etc/bsky-bots/global.yaml ]] || cp "${tmpdir}/configs/global.yaml" /etc/bsky-bots/global.yaml
[[ -f /etc/bsky-bots/bots.yaml   ]] || cp "${tmpdir}/configs/bots.yaml"   /etc/bsky-bots/bots.yaml
[[ -f /etc/bsky-bots.env         ]] || cp "${tmpdir}/configs/bsky-bots.env.example" /etc/bsky-bots.env

chgrp bskybots /etc/bsky-bots /etc/bsky-bots.env || true
chmod 750 /etc/bsky-bots
chmod 640 /etc/bsky-bots/*.yaml /etc/bsky-bots.env || true

# systemd
cp "${tmpdir}/systemd/bsky-bots.service" /etc/systemd/system/bsky-bots.service
systemctl daemon-reload
systemctl enable bsky-bots

echo
echo "[*] Install complete."
echo "Next steps:"
echo "  1) Edit /etc/bsky-bots.env and set OPENAI_API_KEY"
echo "  2) Edit /etc/bsky-bots/bots.yaml (handle/app_password etc.)"
echo "  3) Start the service:   sudo systemctl start bsky-bots"
echo "     Check logs:          sudo journalctl -u bsky-bots -f"
echo
echo "Tip: Approval UI (if enabled) runs on 0.0.0.0:8787 (put it behind Nginx if public)."
