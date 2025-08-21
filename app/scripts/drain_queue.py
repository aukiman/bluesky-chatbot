#!/usr/bin/env python3
import argparse, time, yaml
from bskybots.core import store
from bskybots.core.bsky_client import BskyClient

CONFIG_BOTS = "/etc/bsky-bots/bots.yaml"

def load_bots():
    with open(CONFIG_BOTS, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def cfg_for(handle, cfg):
    for b in cfg.get("bots", []):
        if b.get("handle") == handle:
            return b
    raise SystemExit(f"Bot config not found for handle: {handle}")

def login(handle, cfg):
    b = cfg_for(handle, cfg)
    identifier = b.get("identifier") or b["handle"]
    service = b.get("service")
    return BskyClient(identifier, b["app_password"], service=service)

def is_notfound(err: Exception) -> bool:
    s = str(err)
    return ("NotFound" in s) or ("Post not found" in s)

def main():
    ap = argparse.ArgumentParser(description="Drain queued (retry) replies.")
    ap.add_argument("--bot", help="Limit to this bot handle")
    ap.add_argument("--max", type=int, default=50, help="Max items to post this run")
    ap.add_argument("--sleep", type=float, default=10.0, help="Seconds between posts")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    store.init_db()
    cfg = load_bots()
    posted = 0
    while posted < args.max:
        batch = store.list_queue_multi(["retry"], bot_handle=args.bot, limit=min(10, args.max - posted))
        if not batch:
            print("No retry items remaining.")
            break

        clients = {}
        for it in batch:
            bot_handle = it["bot_handle"]
            print(f"-> #{it['id']} bot={bot_handle} author={it['author_handle']}")
            if args.dry_run:
                continue

            if bot_handle not in clients:
                clients[bot_handle] = login(bot_handle, cfg)
            cli = clients[bot_handle]

            try:
                cli.send_reply(it["llm_reply"], it["parent_uri"])
                store.set_queue_status(it["id"], "posted")
                store.log_action(bot_handle, "reply", target_uri=it["parent_uri"], note=(it["llm_reply"] or "")[:140])
                posted += 1
                print(f"   posted (total this run: {posted})")
                time.sleep(args.sleep)
                if posted >= args.max:
                    break
            except Exception as e:
                if is_notfound(e):
                    print("   gone (marking as gone; will not retry)")
                    store.set_queue_status(it["id"], "gone")
                else:
                    print(f"   error: {e}; will retry later")
                time.sleep(max(2.0, args.sleep))

    print(f"Done. Posted {posted} this run.")
if __name__ == "__main__":
    main()
