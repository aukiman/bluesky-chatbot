import re
from .utils import looks_political, looks_nsfw

def hashtags(text):
    return re.findall(r"#(\\w+)", text or "")

def allow_post(text, author, allow_unprompted, nsfw_allowed, allow, block):
    # block lists
    if looks_political(text):
        return False
    if looks_nsfw(text) and not nsfw_allowed:
        return False
    low = (text or "").lower()
    if author and author.lower() in [u.lower() for u in block.get("users", [])]:
        return False
    for p in block.get("phrases", []):
        if p.lower() in low:
            return False
    hset = set([h.lower() for h in hashtags(text)])
    if hset & set([h.lower().lstrip("#") for h in block.get("hashtags", [])]):
        return False

    # allow lists (if any present, they narrow the scope)
    has_allow = any([allow.get("users"), allow.get("phrases"), allow.get("hashtags")])
    if has_allow:
        ok = False
        if author and allow.get("users") and author.lower() in [u.lower() for u in allow.get("users", [])]:
            ok = True
        if not ok and any(p.lower() in low for p in allow.get("phrases", [])):
            ok = True
        if not ok and (hset & set([h.lower().lstrip("#") for h in allow.get("hashtags", [])])):
            ok = True
        if not ok:
            return False

    return bool(allow_unprompted)
