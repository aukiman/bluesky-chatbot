import logging, yaml
from pathlib import Path
from ..core.bsky_client import BskyClient
from ..core.openai_client import OpenAIClient
from ..core.rate_limiter import RateLimiter
from ..core import store
from ..core.utils import now_iso, apply_persona
from ..core.filters import allow_post

def _resolve_approval_mode(bot_cfg, global_cfg):
    db_override = store.get_state("approval.%s" % bot_cfg['handle'])
    if db_override in ("on","off"): return db_override == "on"
    if "approval_mode" in bot_cfg: return bool(bot_cfg["approval_mode"])
    return bool(global_cfg.get("approval_mode", False))

class BotWorker:
    def __init__(self, bot_cfg, global_cfg, system_prompt_path):
        self.cfg = bot_cfg; self.global_cfg = global_cfg
        self.nsfw_allowed = bool(bot_cfg.get("nsfw_allowed", False))
        self.bot_handle = bot_cfg["handle"]

        identifier = bot_cfg.get("identifier") or bot_cfg["handle"]
        service = bot_cfg.get("service")
        self.client = BskyClient(identifier, bot_cfg["app_password"], service=service)

        with open(system_prompt_path, "r", encoding="utf-8") as f: system_prompt = f.read()
        model = global_cfg.get("openai", {}).get("model", "gpt-4o-mini")
        temp = float(global_cfg.get("openai", {}).get("temperature", 0.7))
        self.llm = OpenAIClient(model=model, temperature=temp, system_prompt=system_prompt)

        rate = bot_cfg.get("rate_limit", {"max_per_minute": 10, "max_per_hour": 100})
        self.limiter_min = RateLimiter(rate.get("max_per_minute", 10), 60)
        self.limiter_hour = RateLimiter(rate.get("max_per_hour", 100), 3600)
        # throttle LLM calls (configurable in global.yaml)
        self.llm_limiter = RateLimiter(int(global_cfg.get("llm_rate_limit_per_minute", 20)), 60)

        self.sleep_seconds = int(global_cfg.get("loop_sleep_seconds", 20))
        Path("/var/log/bsky-bots").mkdir(parents=True, exist_ok=True)
        self.persona = bot_cfg.get("persona", {"tone":"warm","emoji_density":1,"formality":1,"humour":1})
        self.allow = bot_cfg.get("allow", {"users":[],"phrases":[],"hashtags":[]})
        self.block = bot_cfg.get("block", {"users":[],"phrases":[],"hashtags":[]})

    def _limited(self):
        # PEEK only (do not consume)
        return not (self.limiter_min.can() and self.limiter_hour.can())

    def _reserve_slot(self):
        # CONSUME a slot in both windows
        return self.limiter_min.take() and self.limiter_hour.take()

    def _post_or_queue(self, reply_text, parent_uri, author_handle, source, original_text):
        approval = _resolve_approval_mode(self.cfg, self.global_cfg)
        if approval:
            store.queue_reply(self.bot_handle, parent_uri, author_handle, source, original_text, reply_text, extra={})
            logging.info("[%s] queued reply for approval to %s", self.bot_handle, parent_uri); return
        if self._limited():
            logging.info("[%s] Rate limited, queueing for retry.", self.bot_handle)
            store.queue_reply(self.bot_handle, parent_uri, author_handle, source, original_text, reply_text, status="retry")
            return
        if not self._reserve_slot():
            logging.info("[%s] Slot reservation failed; queueing for retry.", self.bot_handle)
            store.queue_reply(self.bot_handle, parent_uri, author_handle, source, original_text, reply_text, status="retry")
            return
        res = self.client.send_reply(reply_text, parent_uri)
        store.log_action(self.bot_handle, "reply", target_uri=parent_uri, note=reply_text[:140])
        logging.info("[%s] Replied to %s", self.bot_handle, parent_uri); return res

    def _memory_for(self, user_handle):
        return store.get_memory(self.bot_handle, user_handle)

    def _update_memory(self, user_handle, last_post_text, last_reply_text):
        mem = store.get_memory(self.bot_handle, user_handle); history = mem.get("history", [])
        history.append({"post": last_post_text[:300], "reply": last_reply_text[:300]}); history = history[-6:]
        store.upsert_memory(self.bot_handle, user_handle, {"history": history})

    def _drain_queue(self):
        # try to post a few queued items for this bot when capacity allows
        items = store.list_queue_multi(["retry"], bot_handle=self.bot_handle, limit=5)
        for it in items:
            if self._limited(): return
            if not self._reserve_slot(): return
            try:
                self.client.send_reply(it["llm_reply"], it["parent_uri"])
                store.set_queue_status(it["id"], "posted")
                store.log_action(self.bot_handle, "reply", target_uri=it["parent_uri"], note=(it["llm_reply"] or "")[:140])
                logging.info("[%s] Drained queued reply id=%s", self.bot_handle, it["id"])
            except Exception:
                # keep status=retry for next loop
                break

    def run_once(self):
        # First drain any backlog created by rate limits
        self._drain_queue()

        notifications = self.client.list_mentions_and_replies(limit=50)
        for n in notifications:
            uri = n.uri
            if store.is_seen(uri): continue
            store.mark_seen(uri)
            reason = getattr(n, "reason", "")
            record = getattr(n, "record", None)
            text = getattr(record, "text", "") if record else ""
            author = getattr(n, "author", None)
            author_name = getattr(author, "handle", "user") if author else "user"
            if reason not in ("mention","reply"): continue

            # throttle LLM
            if not self.llm_limiter.can():
                logging.info("[LLM] throttled; skipping classify this cycle")
                continue
            self.llm_limiter.take()

            thread_ctx = self._memory_for(author_name)
            data = self.llm.classify_and_generate(text=text, author=author_name, nsfw_allowed=self.nsfw_allowed, persona=self.persona, thread_context=thread_ctx, target_lang="en")
            if data.get("should_reply") and data.get("reply"):
                final_reply = apply_persona(data["reply"], self.persona)
                try:
                    self._post_or_queue(final_reply, parent_uri=uri, author_handle=author_name, source=reason, original_text=text)
                    self._update_memory(author_name, text, final_reply)
                except Exception as e:
                    logging.exception("Failed to handle reply: %s", e)

        try: self.client.mark_notifications_seen()
        except Exception: pass

        # Optional unprompted search
        rules = self.cfg.get("reply_rules", {})
        allow_unprompted = bool(rules.get("allow_unprompted", False))
        keywords = rules.get("keywords", [])
        since = store.get_state("since_%s" % self.bot_handle)
        if allow_unprompted and keywords:
            for kw in keywords:
                try: posts = self.client.search_posts(query=kw, since=since, limit=20)
                except Exception: posts = []
                for p in posts or []:
                    author_handle = getattr(getattr(p, "author", None), "handle", "user")
                    if author_handle == self.bot_handle: continue
                    if store.is_seen(p.uri): continue
                    store.mark_seen(p.uri)
                    text = getattr(getattr(p, "record", None), "text", "")
                    if not allow_post(text, author_handle, True, self.nsfw_allowed, self.allow, self.block): continue

                    # throttle LLM
                    if not self.llm_limiter.can():
                        logging.info("[LLM] throttled; skipping classify this cycle")
                        continue
                    self.llm_limiter.take()

                    thread_ctx = self._memory_for(author_handle)
                    data = self.llm.classify_and_generate(text=text, author=author_handle, nsfw_allowed=self.nsfw_allowed, persona=self.persona, thread_context=thread_ctx, target_lang="en")
                    if data.get("should_reply") and data.get("reply"):
                        final_reply = apply_persona(data["reply"], self.persona)
                        try:
                            self._post_or_queue(final_reply, parent_uri=p.uri, author_handle=author_handle, source="search", original_text=text)
                            self._update_memory(author_handle, text, final_reply)
                        except Exception as e:
                            logging.exception("Failed to post unprompted reply: %s", e)

            store.set_state("since_%s" % self.bot_handle, now_iso())
