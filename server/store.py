"""洞察织机(InsightLoom)状态存储:SQLite(队列/事件/提案)+ vault Markdown 落盘。

设计原则:
- 知识本体永远只是磁盘上的 Markdown 文件(vault/),零锁定,Obsidian 可直接打开
- SQLite 只存"过程状态":收件箱队列、Agent 活动事件、待审批提案
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from . import config

DATA_DIR = Path(config.env("DATA_DIR", str(Path(__file__).resolve().parent.parent / "data")))
VAULT_DIR = Path(config.env("VAULT_DIR", str(Path(__file__).resolve().parent.parent / "vault")))
DATA_DIR.mkdir(parents=True, exist_ok=True)
VAULT_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "loom.db"

# 品牌迁移:旧数据文件 curator.db(含 WAL 边车)自动改名为 loom.db,数据无损
for _suffix in ("", "-wal", "-shm"):
    _legacy = DATA_DIR / f"curator.db{_suffix}"
    _target = DATA_DIR / f"loom.db{_suffix}"
    if _legacy.exists() and not _target.exists():
        _legacy.rename(_target)

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS items(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT DEFAULT '',
                content TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                agent TEXT NOT NULL,
                message TEXT NOT NULL,
                level TEXT DEFAULT 'info',
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS proposals(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                filepath TEXT NOT NULL,
                markdown TEXT NOT NULL,
                verdict TEXT DEFAULT '',
                links TEXT DEFAULT '[]',
                status TEXT DEFAULT 'pending',
                created_at REAL NOT NULL
            );
            """
        )
        # 迁移:老库补 kind 列(new_note=新建笔记 / link_suggestion=园丁双链建议)
        try:
            _conn.execute("ALTER TABLE proposals ADD COLUMN kind TEXT DEFAULT 'new_note'")
        except sqlite3.OperationalError:
            pass  # 列已存在
        _conn.commit()
    return _conn


# ---------------- items ----------------

def create_item(title: str, content: str, url: str = "") -> int:
    with _lock:
        cur = _db().execute(
            "INSERT INTO items(title,url,content,status,created_at) VALUES(?,?,?,'pending',?)",
            (title, url, content, time.time()),
        )
        _db().commit()
        return int(cur.lastrowid)


def set_item_status(item_id: int, status: str) -> None:
    with _lock:
        _db().execute("UPDATE items SET status=? WHERE id=?", (status, item_id))
        _db().commit()


def get_item(item_id: int) -> dict[str, Any] | None:
    row = _db().execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    return dict(row) if row else None


def list_items(limit: int = 100) -> list[dict[str, Any]]:
    rows = _db().execute("SELECT * FROM items ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


# ---------------- events ----------------

def log_event(item_id: int, agent: str, message: str, level: str = "info") -> None:
    with _lock:
        _db().execute(
            "INSERT INTO events(item_id,agent,message,level,created_at) VALUES(?,?,?,?,?)",
            (item_id, agent, message, level, time.time()),
        )
        _db().commit()


def list_events(limit: int = 80) -> list[dict[str, Any]]:
    rows = _db().execute(
        "SELECT e.*, i.title AS item_title FROM events e LEFT JOIN items i ON i.id=e.item_id "
        "ORDER BY e.id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------- proposals ----------------

def create_proposal(
    item_id: int,
    filepath: str,
    markdown: str,
    verdict: str,
    links: list[str],
    kind: str = "new_note",
) -> int:
    with _lock:
        cur = _db().execute(
            "INSERT INTO proposals(item_id,filepath,markdown,verdict,links,status,created_at,kind) "
            "VALUES(?,?,?,?,?,'pending',?,?)",
            (item_id, filepath, markdown, verdict, json.dumps(links, ensure_ascii=False), time.time(), kind),
        )
        _db().commit()
        return int(cur.lastrowid)


def get_proposal(pid: int) -> dict[str, Any] | None:
    row = _db().execute("SELECT * FROM proposals WHERE id=?", (pid,)).fetchone()
    if row:
        d = dict(row)
        d["links"] = json.loads(d.get("links") or "[]")
        return d
    return None


def set_proposal_status(pid: int, status: str) -> None:
    with _lock:
        _db().execute("UPDATE proposals SET status=? WHERE id=?", (status, pid))
        _db().commit()


def list_proposals(status: str | None = None) -> list[dict[str, Any]]:
    if status:
        rows = _db().execute(
            "SELECT * FROM proposals WHERE status=? ORDER BY id DESC", (status,)
        ).fetchall()
    else:
        rows = _db().execute("SELECT * FROM proposals ORDER BY id DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["links"] = json.loads(d.get("links") or "[]")
        out.append(d)
    return out


# ---------------- vault ----------------

def slugify(title: str) -> str:
    # 中文友好 slug:保留中文/字母/数字,其余变 -
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "-", title).strip("-")
    return (s or "note")[:60]


def write_vault_note(filename: str, markdown: str) -> str:
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    path = VAULT_DIR / f"{filename}.md"
    i = 1
    while path.exists():  # 防覆盖
        path = VAULT_DIR / f"{filename}-{i}.md"
        i += 1
    path.write_text(markdown, encoding="utf-8")
    return path.name


def append_to_vault_note(filename: str, line: str) -> str:
    """园丁提案批准后:在既有笔记追加双链(幂等,不重复追加)。"""
    path = VAULT_DIR / filename
    if not path.exists():
        raise FileNotFoundError(filename)
    text = path.read_text(encoding="utf-8")
    if line in text:  # 幂等
        return filename
    section = "## 关联笔记(🌻 园丁建议)"
    if section not in text:
        text = text.rstrip("\n") + f"\n\n{section}\n{line}\n"
    else:
        text = text.rstrip("\n") + f"\n{line}\n"
    path.write_text(text, encoding="utf-8")
    return filename


def list_vault_notes() -> list[str]:
    return sorted(p.name for p in VAULT_DIR.glob("*.md"))


def read_vault_note(name: str) -> str:
    p = VAULT_DIR / name
    if p.exists():
        return p.read_text(encoding="utf-8")[:2000]
    return ""
