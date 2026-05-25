import sqlite3
import os
from datetime import datetime
from typing import Optional

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
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
    """Restore a previously deleted/marked record by re-inserting it."""
    conn = _connect()
    conn.execute(
        "INSERT INTO song_requests (song_name, sender_name, battery, bv_number, status, sort_order) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (record["song_name"], record.get("sender_name", ""),
         record.get("battery", 0), record.get("bv_number", ""),
         record.get("status", "pending"), record.get("sort_order", 0))
    )
    conn.commit()
    conn.close()
