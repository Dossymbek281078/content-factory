"""Очередь роликов в SQLite: queued -> rendered -> uploaded (или failed)."""

import sqlite3

from . import config

# Сбой чаще всего временный (сеть, лимит API), поэтому упавший ролик повторяется при следующих
# запусках; после MAX_ATTEMPTS сбоев он остаётся failed и не запирает очередь.
MAX_ATTEMPTS = 3

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    script_json TEXT,
    video_path TEXT,
    youtube_id TEXT,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


def connect() -> sqlite3.Connection:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(config.DATA_DIR / "queue.db")
    db.row_factory = sqlite3.Row
    db.execute(SCHEMA)
    if "attempts" not in {column["name"] for column in db.execute("PRAGMA table_info(videos)")}:
        with db:
            db.execute("ALTER TABLE videos ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")
    return db


def add(db, topic: str) -> int:
    with db:
        return db.execute("INSERT INTO videos (topic) VALUES (?)", (topic,)).lastrowid


def by_status(db, status: str, limit: int | None = None) -> list[sqlite3.Row]:
    sql = "SELECT * FROM videos WHERE status = ? ORDER BY id"
    return db.execute(sql + (f" LIMIT {int(limit)}" if limit else ""), (status,)).fetchall()


def runnable(db, limit: int | None = None) -> list[sqlite3.Row]:
    """Очередь и упавшие ролики, у которых ещё остались попытки.

    Попытка засчитывается до сборки (см. cmd_run), поэтому ролик, чей контейнер убили посреди
    сборки, остаётся queued с израсходованной попыткой и тоже упирается в предел."""
    sql = "SELECT * FROM videos WHERE status IN ('queued', 'failed') AND attempts < ? ORDER BY id"
    return db.execute(sql + (f" LIMIT {int(limit)}" if limit else ""), (MAX_ATTEMPTS,)).fetchall()


def get(db, video_id: int) -> sqlite3.Row | None:
    return db.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()


def everything(db) -> list[sqlite3.Row]:
    return db.execute("SELECT * FROM videos ORDER BY id").fetchall()


def update(db, video_id: int, **fields) -> None:
    columns = ", ".join(f"{name} = ?" for name in fields)
    with db:
        db.execute(f"UPDATE videos SET {columns}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                   (*fields.values(), video_id))
