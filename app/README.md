# Bluesky Conversational Bot System (v2)

Multi-bot Bluesky chatbot runner for Ubuntu 20.04+. Uses the Bluesky API for I/O and OpenAI for composing short, positive, human-like replies.

## New in v2
- **Approval mode + local web UI** (FastAPI at `http://127.0.0.1:9876`) with per-bot toggle
- **Persona presets per bot**: `tone`, `emoji_density`, `formality`, `humour`
- **Block/Allow lists**: users, phrases, hashtags
- **Thread memory**: lightweight per-user context stored in SQLite
- **Firehose listener**: optional service storing candidate posts for smarter selection (best-effort placeholder)

## One-liner install (after pushing to GitHub)
```bash
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/<USER>/<REPO>/main/install.sh)"
```

## Configure
- `/etc/bsky-bots/bots.yaml` (per-bot auth + persona + lists + rate limits)
- `/etc/bsky-bots/global.yaml` (model/temperature/loop interval, `approval_mode`, `enable_firehose`, `ui_port`)
- `/etc/bsky-bots.env` (set `OPENAI_API_KEY`)

## Start
```bash
sudo systemctl start bsky-bots bsky-bots-ui bsky-firehose
sudo systemctl status bsky-bots
```

Open the UI at **http://127.0.0.1:9876** to approve or reject queued replies, and to toggle approval ON/OFF per bot.

## Thread memory
We retain a short rolling history of interactions per user (last ~6 turns) and pass a minimal summary to the LLM to keep context.

## Block/Allow
- If any allow-lists are set, unprompted replies require a match (user, phrase, OR hashtag).
- Block-lists apply to both prompted & unprompted.

## Firehose
The included listener is a **best-effort placeholder** and may need swapping for a production-grade feed parser or aggregator. If `enable_firehose` is not needed, you can disable the service.

## Uninstall
```bash
sudo systemctl disable --now bsky-bots bsky-bots-ui bsky-firehose
sudo rm -f /etc/systemd/system/bsky-bots*.service /etc/systemd/system/bsky-firehose.service
sudo rm -rf /opt/bsky-bots /var/lib/bsky-bots /var/log/bsky-bots /etc/bsky-bots /etc/bsky-bots.env
sudo userdel bskybots || true
sudo systemctl daemon-reload
```
