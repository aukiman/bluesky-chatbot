#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo ./install.sh"
  exit 1
fi

echo "[*] Installing system dependencies..."
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip git

# Create user & dirs
id -u bskybots >/dev/null 2>&1 || useradd -r -s /usr/sbin/nologin -d /opt/bsky-bots bskybots || true
install -d -o bskybots -g bskybots /opt/bsky-bots
install -d -o bskybots -g bskybots /var/lib/bsky-bots
install -d -o bskybots -g bskybots /var/log/bsky-bots
install -d -o bskybots -g bskybots /etc/bsky-bots

echo "[*] Copying files..."
cp -r bskybots /opt/bsky-bots/
cp -r prompts /opt/bsky-bots/
cp -r templates /opt/bsky-bots/
cp -r static /opt/bsky-bots/
cp scripts/bsky-bots.py /opt/bsky-bots/
cp scripts/bsky-bots-ui.py /opt/bsky-bots/
cp scripts/bsky-firehose.py /opt/bsky-bots/
chown -R bskybots:bskybots /opt/bsky-bots

# Python venv
echo "[*] Setting up Python venv..."
sudo -u bskybots python3 -m venv /opt/bsky-bots/.venv
/opt/bsky-bots/.venv/bin/pip install --upgrade pip wheel setuptools
/opt/bsky-bots/.venv/bin/pip install -r requirements.txt

# Config templates
echo "[*] Installing config templates (edit these) ..."
[[ -f /etc/bsky-bots/bots.yaml ]] || cp config/bots.example.yaml /etc/bsky-bots/bots.yaml
[[ -f /etc/bsky-bots/global.yaml ]] || cp config/global.example.yaml /etc/bsky-bots/global.yaml
chmod 600 /etc/bsky-bots/*.yaml

# Env file for OPENAI_API_KEY
if [[ ! -f /etc/bsky-bots.env ]]; then
  cat >/etc/bsky-bots.env <<'EOF'
# Set your OpenAI API key here
OPENAI_API_KEY=sk-yourkey
EOF
  chmod 600 /etc/bsky-bots.env
fi

# Systemd services
echo "[*] Installing systemd services..."
cp systemd/bsky-bots.service /etc/systemd/system/bsky-bots.service
cp systemd/bsky-bots-ui.service /etc/systemd/system/bsky-bots-ui.service
cp systemd/bsky-firehose.service /etc/systemd/system/bsky-firehose.service
systemctl daemon-reload
systemctl enable bsky-bots.service
systemctl enable bsky-bots-ui.service
systemctl enable bsky-firehose.service

echo "[*] Installation complete."
echo "Edit /etc/bsky-bots/bots.yaml and /etc/bsky-bots.env, then start with: sudo systemctl start bsky-bots bsky-bots-ui bsky-firehose"
