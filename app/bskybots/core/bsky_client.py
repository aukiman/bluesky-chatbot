import re
from atproto import Client, models
from .utils import now_iso

class BskyClient:
    """
    Wrapper around atproto.Client with optional custom PDS. 
    Uses getPostThread(uri=...) to build ReplyRef, then send_post(...).
    """
    def __init__(self, identifier: str, app_password: str, service: str = None):
        self.client = Client(base_url=service) if service else Client()
        self.profile = self.client.login(identifier, app_password)
        self.handle = self.profile.handle
        self.did = self.profile.did

    # ---------- helpers ----------
    def _normalize_at_uri(self, s: str) -> str:
        if not s: return s
        s = s.strip()
        if s.startswith("at://"): return s
        if "bsky.app/profile/" in s:
            m = re.search(r"/profile/([^/]+)/post/([^/?#]+)", s)
            if m:
                actor, rkey = m.group(1), m.group(2)
                if actor.startswith("did:"):
                    did = actor
                else:
                    params = models.ComAtprotoIdentityResolveHandle.Params(handle=actor)
                    did = self.client.com.atproto.identity.resolve_handle(params).did
                return f"at://{did}/app.bsky.feed.post/{rkey}"
        return s

    def _reply_ref(self, uri: str):
        """
        Build a ReplyRef using getPostThread(uri=...), which gives us the CIDs.
        Avoids older paths that expect repo/rkey directly.
        """
        uri = self._normalize_at_uri(uri)
        try:
            params = models.AppBskyFeedGetPostThread.Params(uri=uri, depth=0, parent_height=10)
        except TypeError:
            params = models.AppBskyFeedGetPostThread.Params(uri=uri, depth=0)
        thread = self.client.app.bsky.feed.get_post_thread(params=params)

        node = thread.thread  # union: should be ThreadViewPost
        def post_of(n):
            return getattr(n, "post", None) if n else None

        parent_post = post_of(node)
        # Walk to root if there's a parent chain
        root_node = node
        while hasattr(root_node, "parent") and getattr(root_node.parent, "post", None):
            root_node = root_node.parent
        root_post = post_of(root_node) or parent_post

        parent_ref = models.create_strong_ref(parent_post)
        root_ref   = models.create_strong_ref(root_post)
        return models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=root_ref)

    # ---------- API ----------
    def list_mentions_and_replies(self, limit: int = 50):
        params = models.AppBskyNotificationListNotifications.Params(
            limit=limit, reasons=["mention", "reply"]
        )
        res = self.client.app.bsky.notification.list_notifications(params=params)
        return res.notifications or []

    def mark_notifications_seen(self):
        data = models.AppBskyNotificationUpdateSeen.Data(seen_at=now_iso())
        self.client.app.bsky.notification.update_seen(data)

    def search_posts(self, query: str, since: str = None, limit: int = 20):
        params = models.AppBskyFeedSearchPosts.Params(q=query, limit=limit)
        res = self.client.app.bsky.feed.search_posts(params)
        return res.posts or []

    def send_reply(self, text: str, parent_uri: str):
        """
        Robust reply compatible with atproto_client/atproto:
        - Build ReplyRef from getPostThread(uri)
        - Use high-level send_post(...)
        """
        text = (text or "")[:300]
        reply_ref = self._reply_ref(parent_uri)
        # High-level helper composes createRecord correctly across SDK versions
        return self.client.send_post(text=text, reply_to=reply_ref, langs=["en"])
