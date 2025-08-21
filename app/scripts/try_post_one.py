#!/usr/bin/env python3
import sqlite3, yaml, os, sys, traceback
from bskybots.core.bsky_client import BskyClient

DB="/var/lib/bsky-bots/bots.db"; CFG="/etc/bsky-bots/bots.yaml"

def pick_bot_cfg():
    cfg=yaml.safe_load(open(CFG)) or {}
    return (cfg.get("bots") or [])[0]

def main():
    bot = pick_bot_cfg()
    ident = bot.get("identifier") or bot["handle"]
    cli = BskyClient(ident, bot["app_password"], service=bot.get("service"))

    conn = sqlite3.connect(DB)
    row = conn.execute("SELECT id, parent_uri, llm_reply, author_handle FROM reply_queue WHERE status='retry' ORDER BY id ASC LIMIT 1").fetchone()
    if not row:
        print("No retry items."); return
    rid, uri, reply, author = row
    print(f"Testing id={rid} uri={uri} author={author}")
    try:
        res = cli.send_reply(reply, uri)
        print("SUCCESS:", res)
        conn.execute("UPDATE reply_queue SET status='posted' WHERE id=?", (rid,))
        conn.commit()
    except Exception as e:
        print("FAILED:", type(e).__name__, e)
        traceback.print_exc()

if __name__ == "__main__":
    main()
