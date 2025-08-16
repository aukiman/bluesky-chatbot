#!/usr/bin/env bash
set -euo pipefail

# Minimal installer for a 3-file repo: tarball + install.sh + README.md
: "${REPO_USER:=aukiman}"
: "${REPO_NAME:=bluesky-chatbot}"
: "${BRANCH:=main}"
: "${TARBALL_NAME:=bsky-bots-v2.tar.gz}"
: "${TARBALL_URL:=https://raw.githubusercontent.com/${REPO_USER}/${REPO_NAME}/${BRANCH}/${TARBALL_NAME}}"

INSTALL_DIR="/opt/bsky-bots"
ETC_DIR="/etc/bsky-bots"
VAR_LIB="/var/lib/bsky-bots"
VAR_LOG="/var/log/bsky-bots"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo ./install.sh"
  exit 1
fi

echo "[*] Installing system dependencies (Ubuntu 20.04+)..."
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3 python3-venv python3-pip git ca-certificates \
  build-essential python3-dev libffi-dev libssl-dev
update-ca-certificates || true

echo "[*] Creating system user and directories..."
id -u bskybots >/dev/null 2>&1 || useradd -r -s /usr/sbin/nologin -d "${INSTALL_DIR}" bskybots || true
install -d -o bskybots -g bskybots "${INSTALL_DIR}" "${ETC_DIR}" "${VAR_LIB}" "${VAR_LOG}"

TMPDIR="$(mktemp -d)"
cleanup() { rm -rf "${TMPDIR}" || true; }
trap cleanup EXIT

echo "[*] Downloading tarball:"
echo "    ${TARBALL_URL}"
curl -fL "${TARBALL_URL}" -o "${TMPDIR}/${TARBALL_NAME}"

echo "[*] Unpacking to ${INSTALL_DIR} ..."
if [[ -d "${INSTALL_DIR}/bskybots" || -f "${INSTALL_DIR}/requirements.txt" ]]; then
  TS="$(date +%s)"
  echo "    Found existing install. Backing up to ${INSTALL_DIR}.bak-${TS}"
  mv "${INSTALL_DIR}" "${INSTALL_DIR}.bak-${TS}"
  install -d -o bskybots -g bskybots "${INSTALL_DIR}"
fi

tar -xzf "${TMPDIR}/${TARBALL_NAME}" -C "${INSTALL_DIR}" --strip-components=1
chown -R bskybots:bskybots "${INSTALL_DIR}"

echo "[*] Setting up Python virtualenv..."
sudo -u bskybots python3 -m venv "${INSTALL_DIR}/.venv"
"${INSTALL_DIR}/.venv/bin/pip" install --upgrade pip wheel setuptools
if [[ -f "${INSTALL_DIR}/requirements.txt" ]]; then
  "${INSTALL_DIR}/.venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt"
else
  echo "[!] requirements.txt missing in tarball; installing minimal runtime deps..."
  "${INSTALL_DIR}/.venv/bin/pip" install atproto openai PyYAML tenacity httpx uvloop ujson fastapi uvicorn websockets jinja2
fi

echo "[*] Installing config templates to ${ETC_DIR} ..."
[[ -f "${ETC_DIR}/bots.yaml" ]]   || cp "${INSTALL_DIR}/config/bots.example.yaml"   "${ETC_DIR}/bots.yaml"
[[ -f "${ETC_DIR}/global.yaml" ]] || cp "${INSTALL_DIR}/config/global.example.yaml" "${ETC_DIR}/global.yaml"
chmod 600 "${ETC_DIR}"/*.yaml || true

if [[ ! -f /etc/bsky-bots.env ]]; then
  cat >/etc/bsky-bots.env <<'EOF_ENV'
# OpenAI API Key
OPENAI_API_KEY=sk-yourkey
EOF_ENV
  chmod 600 /etc/bsky-bots.env
fi

echo "[*] Installing systemd services..."
cp "${INSTALL_DIR}/systemd/bsky-bots.service"      /etc/systemd/system/bsky-bots.service
[[ -f "${INSTALL_DIR}/systemd/bsky-bots-ui.service" ]]  && cp "${INSTALL_DIR}/systemd/bsky-bots-ui.service"  /etc/systemd/system/bsky-bots-ui.service || true
[[ -f "${INSTALL_DIR}/systemd/bsky-firehose.service" ]] && cp "${INSTALL_DIR}/systemd/bsky-firehose.service" /etc/systemd/system/bsky-firehose.service || true

systemctl daemon-reload
systemctl enable bsky-bots.service || true
[[ -f /etc/systemd/system/bsky-bots-ui.service ]]  && systemctl enable bsky-bots-ui.service  || true
[[ -f /etc/systemd/system/bsky-firehose.service ]] && systemctl enable bsky-firehose.service || true

echo ""
echo "✅ Install finished."
echo ""
echo "Next steps:"
echo "  1) Edit ${ETC_DIR}/bots.yaml and /etc/bsky-bots.env"
echo "  2) Start services:"
echo "       sudo systemctl start bsky-bots"
echo "       sudo systemctl start bsky-bots-ui      # if present"
echo "       sudo systemctl start bsky-firehose     # if present"
echo ""
echo "Logs: ${VAR_LOG}"
