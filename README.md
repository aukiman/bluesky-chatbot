Bluesky Conversational Bot System (v2)

Multi-bot Bluesky chatbot runner for Ubuntu 20.04+.
Uses the Bluesky API (AT Protocol) for input/output and OpenAI for generating short, positive, human-like replies.

✨ Features

Multiple bots in one runner

Approval mode + local web UI (FastAPI at http://127.0.0.1:9876) with per-bot toggle

Persona presets (tone, emoji_density, formality, humour)

Block/Allow lists (users, phrases, hashtags)

Thread memory (short per-user context in SQLite)

Firehose listener (optional) for smarter candidate discovery

Rate limiting per-bot, respecting Bluesky etiquette

Positive tone, no politics, optional NSFW participation

🚀 One-liner Install (after pushing to GitHub)

Replace <USER> and <REPO> with your GitHub details:

sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/<USER>/<REPO>/main/install.sh)"


The installer will:

Create a bskybots system user

Set up /opt/bsky-bots with a Python venv

Install all dependencies

Drop configs into /etc/bsky-bots/

Install three services:

bsky-bots.service (workers)

bsky-bots-ui.service (approval dashboard)

bsky-firehose.service (optional firehose)

⚙️ Configuration
Global config /etc/bsky-bots/global.yaml
openai:
  model: "gpt-4o-mini"
  temperature: 0.7
loop_sleep_seconds: 20
approval_mode: false     # default; per-bot can override
enable_firehose: true
ui_port: 9876

Bots config /etc/bsky-bots/bots.yaml
bots:
  - handle: "yourbot1.bsky.social"
    app_password: "xxxx-xxxx-xxxx-xxxx"
    nsfw_allowed: false
    approval_mode: true
    persona: { tone: "warm", emoji_density: 1, formality: 1, humour: 1 }
    allow: { users: [], phrases: [], hashtags: [] }
    block: { users: ["spam_account.bsky.social"], phrases: ["giveaway","promocode"], hashtags: ["ad","promo"] }
    rate_limit: { max_per_minute: 8, max_per_hour: 80 }
    reply_rules:
      allow_unprompted: false
      keywords: ["music","your brand","Elevator Primates"]

  - handle: "yourbot2.bsky.social"
    app_password: "xxxx-xxxx-xxxx-xxxx"
    nsfw_allowed: true
    approval_mode: false
    persona: { tone: "edgy", emoji_density: 2, formality: 0, humour: 2 }
    allow: { users: [], phrases: [], hashtags: [] }
    block: { users: [], phrases: [], hashtags: [] }
    rate_limit: { max_per_minute: 5, max_per_hour: 50 }
    reply_rules:
      allow_unprompted: true
      keywords: ["ai art","australia","punk rock"]

Environment config /etc/bsky-bots.env
OPENAI_API_KEY=sk-yourkey

▶️ Start & Status

Start the services:

sudo systemctl start bsky-bots bsky-bots-ui bsky-firehose


Check status:

sudo systemctl status bsky-bots


Logs are written to /var/log/bsky-bots/.

Open the UI at http://127.0.0.1:9876 to approve/reject replies and toggle approval per bot.

🧠 Thread Memory

Keeps a rolling history (last ~6 turns) of interactions with each user

Passed as lightweight JSON to OpenAI for more coherent conversations

🚫 Block / ✅ Allow Lists

Block lists always take precedence (users, phrases, hashtags)

If allow lists are set, at least one must match for an unprompted reply

🌊 Firehose Listener

Optional background service (bsky-firehose.service)

Writes discovered posts into SQLite (candidates table)

Can be disabled in global.yaml if not required

🧹 Uninstall
sudo systemctl disable --now bsky-bots bsky-bots-ui bsky-firehose
sudo rm -f /etc/systemd/system/bsky-bots*.service /etc/systemd/system/bsky-firehose.service
sudo rm -rf /opt/bsky-bots /var/lib/bsky-bots /var/log/bsky-bots /etc/bsky-bots /etc/bsky-bots.env
sudo userdel bskybots || true
sudo systemctl daemon-reload


D
