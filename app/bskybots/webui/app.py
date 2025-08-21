from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import yaml

from ..core import store
from ..core.bsky_client import BskyClient

app = FastAPI(title="Bluesky Bots UI")
templates = Jinja2Templates(directory="/opt/bsky-bots/templates")

app.mount("/static", StaticFiles(directory="/opt/bsky-bots/static"), name="static")

CONFIG_PATH = "/etc/bsky-bots/bots.yaml"

def load_bots_cfg():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def get_bot_password(handle: str):
    cfg = load_bots_cfg()
    for b in cfg.get("bots", []):
        if b.get("handle") == handle:
            return b.get("app_password")
    return None

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    pending = store.list_queue(status="pending")
    overrides = { (h.split('.',1)[0] if False else k): store.get_state(f"approval.{k}") for k in [] }  # placeholder
    return templates.TemplateResponse("queue.html", {"request": request, "items": pending})

@app.post("/api/approve")
def approve(item_id: int = Form(...)):
    item = store.get_queue_item(item_id)
    if not item or item["status"] != "pending":
        return JSONResponse({"ok": False, "error": "Item not found"}, status_code=404)
    handle = item["bot_handle"]
    pw = get_bot_password(handle)
    if not pw:
        return JSONResponse({"ok": False, "error": "Bot config not found"}, status_code=400)
    client = BskyClient(handle, pw)
    client.send_reply(item["llm_reply"], parent_uri=item["parent_uri"])
    store.set_queue_status(item_id, "approved-posted")
    store.log_action(handle, "approved_post", target_uri=item["parent_uri"], note=item["llm_reply"][:140])
    return RedirectResponse("/", status_code=303)

@app.post("/api/reject")
def reject(item_id: int = Form(...)):
    store.set_queue_status(item_id, "rejected")
    return RedirectResponse("/", status_code=303)

@app.post("/api/toggle-approval")
def toggle_approval(handle: str = Form(...), mode: str = Form(...)):
    # mode: on/off
    store.set_state(f"approval.{handle}", "on" if mode == "on" else "off")
    return RedirectResponse("/", status_code=303)
