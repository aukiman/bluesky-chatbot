# Bluesky Conversational Bot System (v2) — Minimal Repo

This repo contains **only three files**:
- `bsky-bots-v2.tar.gz` — the full, ready-to-run system
- `install.sh` — bootstrap installer that downloads & unpacks the tarball, installs deps, and sets up services
- `README.md` — this file

---

## One-liner install (Ubuntu 20.04+)

```copy
curl -fsSL https://raw.githubusercontent.com/aukiman/bluesky-chatbot/main/install.sh | sudo bash
```

> If you fork/rename the repo or branch, override via env vars:
```copy
REPO_USER=yourname REPO_NAME=yourrepo BRANCH=main \
curl -fsSL https://raw.githubusercontent.com/yourname/yourrepo/main/install.sh | sudo bash
```

---

## What the installer does

- Installs required OS packages (Python 3, venv, build tools, SSL/CA, etc.)
- Downloads **`bsky-bots-v2.tar.gz`** from the repo root
- Unpacks to **`/opt/bsky-bots`**
- Creates a Python venv and installs Python dependencies from the bundled `requirements.txt`
- Installs config templates to **`/etc/bsky-bots/`**
- Creates `/etc/bsky-bots.env` to hold your `OPENAI_API_KEY`
- Installs and enables systemd services:
  - `bsky-bots.service`
  - `bsky-bots-ui.service` (approval dashboard), if present
  - `bsky-firehose.service`, if present

Start services after editing configs:

```copy
sudo systemctl start bsky-bots bsky-bots-ui bsky-firehose
sudo systemctl status bsky-bots
```

Logs live in: `/var/log/bsky-bots/`

---

## Expected contents inside the tarball

```
bskybots/            prompts/           config/
scripts/             systemd/           templates/
static/              requirements.txt
```

---

## Troubleshooting

- **Nothing happens with the one-liner**: Ensure `install.sh` is on `main` and the repo is public (or authenticate `curl`).  
- **“Missing required directory …”**: Upload **`bsky-bots-v2.tar.gz`** to the **repo root**.  
- **Permission issues**: Run with `sudo` as shown in the one-liner.
