import argparse, logging, sys, time, yaml
from pathlib import Path
from ..core import store
from .worker_bot import BotWorker

def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def main():
    ap = argparse.ArgumentParser(description="Bluesky multi-bot runner")
    ap.add_argument("--config", "-c", default="/etc/bsky-bots/bots.yaml")
    ap.add_argument("--global-config", "-g", default="/etc/bsky-bots/global.yaml")
    ap.add_argument("--prompt", "-p", default="/opt/bsky-bots/prompts/system_prompt.txt")
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()

    Path("/var/lib/bsky-bots").mkdir(parents=True, exist_ok=True)
    Path("/var/log/bsky-bots").mkdir(parents=True, exist_ok=True)
    store.init_db()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler("/var/log/bsky-bots/bots.log"), logging.StreamHandler(sys.stdout)],
    )

    bots_cfg = load_yaml(args.config) or {}
    global_cfg = load_yaml(args.global_config) or {}
    bots = bots_cfg.get("bots", [])
    if not bots:
        logging.error("No bots configured in %s", args.config)
        sys.exit(2)

    workers = [BotWorker(b, global_cfg, args.prompt) for b in bots]
    if args.once:
        for w in workers:
            w.run_once()
        return

    # simple loop
    sleep_s = int(global_cfg.get("loop_sleep_seconds", 20))
    while True:
        for w in workers:
            try:
                w.run_once()
            except Exception as e:
                logging.exception("Worker crashed: %s", e)
        time.sleep(sleep_s)

if __name__ == "__main__":
    main()
