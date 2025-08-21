import os, json, sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import List, Dict, Any, Optional

DEFAULT_DB = os.environ.get("BSKYBOTS_DB", "/var/lib/bsky-bots/bots.db")

def ensure_dirs():
    Path(DEFAULT_DB).parent.mkdir(parents=True, exist_ok=True)

def init_db(db_path: str = DEFAULT_DB):
    ensure_dirs()
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS posts_seen (uri TEXT PRIMARY KEY, seen_at TEXT)')
        c.execute('''CREATE TABLE IF NOT EXISTS actions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ts TEXT, bot_handle TEXT, action TEXT, target_uri TEXT, note TEXT
                    )''')
        c.execute('CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT)')
        c.execute('''CREATE TABLE IF NOT EXISTS reply_queue (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ts TEXT, bot_handle TEXT, parent_uri TEXT, author_handle TEXT,
                        source TEXT, post_text TEXT, llm_reply TEXT, status TEXT, extra TEXT
                    )''')
        c.execute('''CREATE TABLE IF NOT EXISTS candidates (
                        uri TEXT PRIMARY KEY, ts TEXT, author_handle TEXT, text TEXT, source TEXT
                    )''')
        c.execute('''CREATE TABLE IF NOT EXISTS thread_memory (
                        bot_handle TEXT, user_handle TEXT, memory_json TEXT, updated_ts TEXT,
                        PRIMARY KEY (bot_handle, user_handle)
                    )''')
        conn.commit()

@contextmanager
def get_conn(db_path: str = DEFAULT_DB):
    ensure_dirs()
    conn = sqlite3.connect(db_path)
    try:
        yield conn
    finally:
        conn.commit()
        conn.close()

def mark_seen(uri: str):
    with get_conn() as conn:
        conn.execute('INSERT OR REPLACE INTO posts_seen(uri, seen_at) VALUES(?, datetime("now"))', (uri,))

def is_seen(uri: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute('SELECT 1 FROM posts_seen WHERE uri=?', (uri,))
        return cur.fetchone() is not None

def log_action(bot_handle: str, action: str, target_uri: str = "", note: str = ""):
    with get_conn() as conn:
        conn.execute('INSERT INTO actions(ts, bot_handle, action, target_uri, note) VALUES(datetime("now"),?,?,?,?)',
                     (bot_handle, action, target_uri, note))

def get_state(key: str) -> Optional[str]:
    with get_conn() as conn:
        cur = conn.execute('SELECT value FROM state WHERE key=?', (key,))
        row = cur.fetchone()
        return row[0] if row else None

def set_state(key: str, value: str):
    with get_conn() as conn:
        conn.execute('INSERT OR REPLACE INTO state(key, value) VALUES(?,?)', (key, value))

def queue_reply(bot_handle: str, parent_uri: str, author_handle: str, source: str, post_text: str, llm_reply: str, extra: Optional[Dict[str, Any]] = None, status: str = "pending"):
    with get_conn() as conn:
        conn.execute('INSERT INTO reply_queue(ts, bot_handle, parent_uri, author_handle, source, post_text, llm_reply, status, extra) VALUES(datetime("now"),?,?,?,?,?,?,?,?)',
                     (bot_handle, parent_uri, author_handle, source, post_text, llm_reply, status, json.dumps(extra or {})))

def list_queue(status: str = "pending") -> List[Dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.execute('SELECT id, ts, bot_handle, parent_uri, author_handle, source, post_text, llm_reply, status, extra FROM reply_queue WHERE status=? ORDER BY id ASC', (status,))
        cols = [x[0] for x in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()

        ]

def list_queue_multi(statuses: List[str], bot_handle: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    q = 'SELECT id, ts, bot_handle, parent_uri, author_handle, source, post_text, llm_reply, status, extra FROM reply_queue WHERE status IN (%s)' % (",".join(["?"]*len(statuses)))
    params = list(statuses)
    if bot_handle:
        q += " AND bot_handle=?"
        params.append(bot_handle)
    q += " ORDER BY id ASC LIMIT ?"
    params.append(int(limit))
    with get_conn() as conn:
        cur = conn.execute(q, params)
        cols = [x[0] for x in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

def set_queue_status(item_id: int, status: str):
    with get_conn() as conn:
        conn.execute('UPDATE reply_queue SET status=? WHERE id=?', (status, item_id))

def get_queue_item(item_id: int) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.execute('SELECT id, ts, bot_handle, parent_uri, author_handle, source, post_text, llm_reply, status, extra FROM reply_queue WHERE id=?', (item_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [x[0] for x in cur.description]
        return dict(zip(cols, row))

def upsert_memory(bot_handle: str, user_handle: str, memory_json: Dict[str, Any]):
    with get_conn() as conn:
        conn.execute('INSERT OR REPLACE INTO thread_memory(bot_handle,user_handle,memory_json,updated_ts) VALUES(?,?,?,datetime("now"))',
                     (bot_handle, user_handle, json.dumps(memory_json)))

def get_memory(bot_handle: str, user_handle: str) -> Dict[str, Any]:
    with get_conn() as conn:
        cur = conn.execute('SELECT memory_json FROM thread_memory WHERE bot_handle=? AND user_handle=?', (bot_handle, user_handle))
        row = cur.fetchone()
        return json.loads(row[0]) if row and row[0] else {}
