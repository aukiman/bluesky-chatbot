#!/usr/bin/env bash
set -euo pipefail

# --- Config (override with env vars if needed) ---
REPO_URL="${REPO_URL:-https://github.com/aukiman/bluesky-chatbot.git}"
BRANCH="${BRANCH:-main}"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo ./install.sh"
  exit 1
fi

echo "[*] Installing system dependencies..."
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3 python3-venv python3-pip git ca-certificates \
  build-essential python3-dev libffi-dev libssl-dev
update-ca-certificates || true

TMPDIR="$(mktemp -d)"
cleanup() { rm -rf "$TMPDIR" || true; }
trap cleanup EXIT

echo "[*] Cloning repository: $REPO_URL (branch: $BRANCH)"
git clone --depth=1 -b "$BRANCH" "$REPO_URL" "$TMPDIR/repo"

cd "$TMPDIR/repo"

# Sanity check for required directories
for d in bskybots prompts scripts systemd; do
  if [[ ! -e "$d" ]]; then
    echo "[!] Missing required directory '$d' in repository. Aborting."
    exit 1
  fi
done

# Optional folders
[[ -d templates ]] || mkdir -p templates
[[ -d static     ]] || mkdir -p static
[[ -d config     ]] || mkdir -p config

# Create system user & dirs
id -u bskybots >/dev/null 2>&1 || useradd -r -s /usr/sbin/nologin -d /opt/bsky-bots bskybots || true
install -d -o bskybots -g bskybots /opt/bsky-bots
install -d -o bskybots -g bskybots /var/lib/bsky-bots
install -d -o bskybots -g bskybots /var/log/bsky-bots
install -d -o bskybots -g bskybots /etc/bsky-bots

echo "[*] Copying project files to /opt/bsky-bots..."
cp -r bskybots /opt/bsky-bots/
cp -r prompts  /opt/bsky-bots/
cp -r templates /opt/bsky-bots/ || true
cp -r static    /opt/bsky-bots/ || true
cp scripts/bsky-bots.py     /opt/bsky-bots/
cp scripts/bsky-bots-ui.py  /opt/bsky-bots/ || true
cp scripts/bsky-firehose.py /opt/bsky-bots/ || true
chown -R bskybots:bskybots /opt/bsky-bots

# Python venv
echo "[*] Setting up Python venv..."
sudo -u bskybots python3 -m venv /opt/bsky-bots/.venv
/opt/bsky-bots/.venv/bin/pip install --upgrade pip wheel setuptools

if [[ -f requirements.txt ]]; then
  /opt/bsky-bots/.venv/bin/pip install -r requirements.txt
else
  echo "[!] requirements.txt not found. Installing minimal dependencies..."
  /opt/bsky-bots/.venv/bin/pip install atproto openai PyYAML tenacity httpx uvloop ujson fastapi uvicorn websockets jinja2
fi

# Config templates (fallbacks if repo doesn't include them)
echo "[*] Installing config templates (edit these) ..."
if [[ -f config/bots.example.yaml ]]; then
  [[ -f /etc/bsky-bots/bots.yaml ]] || cp config/bots.example.yaml /etc/bsky-bots/bots.yaml
else
  cat >/etc/bsky-bots/bots.yaml <<'YAML'
bots:
  - handle: "yourbot1.bsky.social"
    app_password: "xxxx-xxxx-xxxx-xxxx"
    nsfw_allowed: false
    approval_mode: true
    persona: { tone: "warm", emoji_density: 1, formality: 1, humour: 1 }
    allow: { users: [], phrases: [], hashtags: [] }
    block: { users: [], phrases: [], hashtags: [] }
    rate_limit: { max_per_minute: 8, max_per_hour: 80 }
    reply_rules:
      allow_unprompted: false
      keywords: ["music","your brand"]
YAML
fi

if [[ -f config/global.example.yaml ]]; then
  [[ -f /etc/bsky-bots/global.yaml ]] || cp config/global.example.yaml /etc/bsky-bots/global.yaml
else
  cat >/etc/bsky-bots/global.yaml <<'YAML'
openai: { model: "gpt-4o-mini", temperature: 0.7 }
loop_sleep_seconds: 20
approval_mode: false
enable_firehose: true
ui_port: 9876
YAML
fi

chmod 600 /etc/bsky-bots/*.yaml || true

# Env file for OPENAI_API_KEY
if [[ ! -f /etc/bsky-bots.env ]]; then
  cat >/etc/bsky-bots.env <<'EOF_ENV'
# Set your OpenAI API key here
OPENAI_API_KEY=sk-yourkey
EOF_ENV
  chmod 600 /etc/bsky-bots.env
fi

# Systemd services (fallback create if missing)
echo "[*] Installing systemd services..."
install_service() {
  local src="$1" dst="$2" fallback="
