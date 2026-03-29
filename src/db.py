"""SQLite database helpers."""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "newsfeed.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guid        TEXT    UNIQUE NOT NULL,
    feed_label  TEXT    NOT NULL,
    title       TEXT    NOT NULL,
    url         TEXT    NOT NULL,
    published_at DATETIME,
    fetched_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    content     TEXT,
    summary     TEXT,
    theme       TEXT,
    tags        TEXT,   -- JSON array
    audio_done  INTEGER DEFAULT 0  -- 1 once OGG generated
);

CREATE INDEX IF NOT EXISTS idx_items_published ON items(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_theme     ON items(theme);
CREATE INDEX IF NOT EXISTS idx_items_fetched   ON items(fetched_at DESC);

CREATE TABLE IF NOT EXISTS digests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    summary     TEXT    NOT NULL,
    items_count INTEGER DEFAULT 0
);
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)


def add_item(guid: str, feed_label: str, title: str, url: str,
             published_at: datetime | None, raw_description: str = "") -> bool:
    """Insert a new item. Returns True if inserted, False if already exists."""
    try:
        with _connect() as conn:
            conn.execute(
                """INSERT INTO items (guid, feed_label, title, url, published_at, content)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (guid, feed_label, title, url, published_at, raw_description),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def get_unsummarized(limit: int = 50) -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM items WHERE summary IS NULL ORDER BY fetched_at DESC LIMIT ?",
            (limit,),
        ).fetchall()


def get_unclassified(limit: int = 50) -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM items WHERE theme IS NULL AND summary IS NOT NULL ORDER BY fetched_at DESC LIMIT ?",
            (limit,),
        ).fetchall()


def update_summary(item_id: int, content: str, summary: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE items SET content = ?, summary = ? WHERE id = ?",
            (content, summary, item_id),
        )


def update_theme(item_id: int, theme: str, tags: list[str]) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE items SET theme = ?, tags = ? WHERE id = ?",
            (theme, json.dumps(tags), item_id),
        )


def get_recent_items(days: int = 3) -> list[sqlite3.Row]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with _connect() as conn:
        return conn.execute(
            """SELECT * FROM items
               WHERE fetched_at >= ? AND summary IS NOT NULL
               ORDER BY published_at DESC""",
            (cutoff,),
        ).fetchall()


def get_all_recent_items(days: int = 3) -> list[sqlite3.Row]:
    """All recent items including those without summaries yet."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM items WHERE fetched_at >= ? ORDER BY published_at DESC",
            (cutoff,),
        ).fetchall()


def get_themes(days: int = 3) -> list[str]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with _connect() as conn:
        rows = conn.execute(
            """SELECT DISTINCT theme FROM items
               WHERE theme IS NOT NULL AND fetched_at >= ?
               ORDER BY theme""",
            (cutoff,),
        ).fetchall()
    return [r["theme"] for r in rows]


def get_items_by_theme(theme: str, days: int = 3) -> list[sqlite3.Row]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with _connect() as conn:
        return conn.execute(
            """SELECT * FROM items
               WHERE theme = ? AND fetched_at >= ?
               ORDER BY published_at DESC""",
            (theme, cutoff),
        ).fetchall()


def save_digest(summary: str, items_count: int) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO digests (summary, items_count) VALUES (?, ?)",
            (summary, items_count),
        )


def get_latest_digest() -> sqlite3.Row | None:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM digests ORDER BY created_at DESC LIMIT 1"
        ).fetchone()


def get_items_needing_audio(limit: int = 80) -> list[sqlite3.Row]:
    """Items that have a summary but no audio file yet."""
    with _connect() as conn:
        return conn.execute(
            """SELECT * FROM items
               WHERE summary IS NOT NULL AND audio_done = 0
               ORDER BY fetched_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()


def mark_audio_done(item_id: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE items SET audio_done = 1 WHERE id = ?", (item_id,))


def cleanup_old_items(days: int = 3) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with _connect() as conn:
        cur = conn.execute("DELETE FROM items WHERE fetched_at < ?", (cutoff,))
        return cur.rowcount
