import hashlib
from datetime import datetime, timezone

POLITICAL_KEYWORDS = [
    "election","senate","parliament","congress","prime minister","president",
    "vote","voting","policy","campaign","minister","referendum","party"
]
NSFW_KEYWORDS = ["nsfw","adult","sex","sext","explicit","nude","porn","xxx","onlyfans"]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def looks_political(text):
    t = (text or "").lower()
    return any(k in t for k in POLITICAL_KEYWORDS)

def looks_nsfw(text):
    t = (text or "").lower()
    return any(k in t for k in NSFW_KEYWORDS)

def apply_persona(reply, persona):
    # light-touch persona post-processing
    if not reply:
        return reply
    emoji_density = int(persona.get("emoji_density", 1))
    formality = int(persona.get("formality", 1))
    r = reply
    if formality == 0:
        r = r.replace("do not","don't").replace("cannot","can't")
    elif formality >= 2:
        r = r.replace("don't","do not").replace("can't","cannot")
    emojis = ["🙂","😄","✨","👍","🙌"]
    if emoji_density > 0:
        r = (r + " " + " ".join(emojis[:emoji_density])).strip()
    return r
