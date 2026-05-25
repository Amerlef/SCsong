import sqlite3
import os
import sys
from typing import Optional

if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_DIR = os.path.join(_BASE_DIR, "data")
DB_PATH = os.path.join(DB_DIR, "songs.db")


def _connect() -> sqlite3.Connection:
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS song_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_name TEXT NOT NULL,
            sender_name TEXT DEFAULT '',
            battery INTEGER DEFAULT 0,
            bv_number TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sort_order INTEGER DEFAULT 0
        )
    """)
    # Migrate old 'suspended' status to 'deploy'
    conn.execute("UPDATE song_requests SET status='deploy' WHERE status='suspended'")
    conn.commit()
    conn.close()


def add_song(song_name: str, sender_name: str = "", battery: int = 0,
             bv_number: str = "") -> dict:
    conn = _connect()
    cur = conn.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM song_requests")
    next_order = cur.fetchone()[0]
    conn.execute(
        "INSERT INTO song_requests (song_name, sender_name, battery, bv_number, sort_order) "
        "VALUES (?, ?, ?, ?, ?)",
        (song_name, sender_name, battery, bv_number, next_order)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM song_requests WHERE id = last_insert_rowid()").fetchone()
    conn.close()
    return dict(row)


def get_pending_songs() -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM song_requests WHERE status='pending' ORDER BY sort_order ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_songs() -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM song_requests ORDER BY sort_order ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_played(song_id: int):
    conn = _connect()
    conn.execute("UPDATE song_requests SET status='played' WHERE id=?", (song_id,))
    conn.commit()
    conn.close()


def mark_skipped(song_id: int):
    conn = _connect()
    conn.execute("UPDATE song_requests SET status='skipped' WHERE id=?", (song_id,))
    conn.commit()
    conn.close()


def delete_song(song_id: int):
    conn = _connect()
    conn.execute("DELETE FROM song_requests WHERE id=?", (song_id,))
    conn.commit()
    conn.close()


def batch_delete_played():
    conn = _connect()
    conn.execute("DELETE FROM song_requests WHERE status IN ('played', 'skipped')")
    conn.commit()
    conn.close()


def restore_last_deleted(record: dict):
    """Restore a previously deleted/marked record. If restoring to pending, put at end of queue."""
    conn = _connect()
    target_status = record.get("status", "pending")
    # When restoring to pending, always put at end of queue
    if target_status == "pending":
        cur = conn.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM song_requests")
        new_order = cur.fetchone()[0]
    else:
        new_order = record.get("sort_order", 0)
    conn.execute(
        "INSERT INTO song_requests (song_name, sender_name, battery, bv_number, status, sort_order) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (record["song_name"], record.get("sender_name", ""),
         record.get("battery", 0), record.get("bv_number", ""),
         target_status, new_order)
    )
    conn.commit()
    conn.close()


def mark_deploy(song_id: int):
    conn = _connect()
    conn.execute("UPDATE song_requests SET status='deploy' WHERE id=?", (song_id,))
    conn.commit()
    conn.close()


def move_to_pending_end(song_id: int):
    """Move a deploy song back to pending at the end of the queue."""
    conn = _connect()
    cur = conn.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM song_requests")
    new_order = cur.fetchone()[0]
    conn.execute(
        "UPDATE song_requests SET status='pending', sort_order=? WHERE id=?",
        (new_order, song_id)
    )
    conn.commit()
    conn.close()


def get_deploy_songs() -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM song_requests WHERE status='deploy' ORDER BY sort_order ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_sort_order(song_id: int, new_order: int):
    conn = _connect()
    conn.execute("UPDATE song_requests SET sort_order=? WHERE id=?", (new_order, song_id))
    conn.commit()
    conn.close()


def reorder_pending(ordered_ids: list[int]):
    """Rewrite sort_order for pending songs based on the given id list order."""
    conn = _connect()
    for i, sid in enumerate(ordered_ids):
        conn.execute("UPDATE song_requests SET sort_order=? WHERE id=?", (i, sid))
    conn.commit()
    conn.close()
