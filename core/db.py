import sqlite3
from datetime import datetime
from pathlib import Path
import pandas as pd

from core.config import DB_PATH


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def db_conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)


def _table_cols(con, table: str) -> list[str]:
    cur = con.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return [r[1] for r in cur.fetchall()]


def init_db():
    con = db_conn()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS drivers (
        driver_id INTEGER PRIMARY KEY,
        driver_name TEXT,
        user_id TEXT,
        start_date TEXT,
        status TEXT DEFAULT 'نشط',
        notes TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)

    # announcements (handle older schema variations via ensure_announcements_schema)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS announcements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        created_by_role TEXT NOT NULL,
        message TEXT
    )
    """)
    con.commit()
    con.close()

    ensure_announcements_schema()


def ensure_announcements_schema():
    con = db_conn()
    cur = con.cursor()
    cols = _table_cols(con, "announcements")

    # Some older versions used "body" or had NOT NULL constraints.
    # We ensure both message/body exist so inserts won't fail.
    if "message" not in cols:
        cur.execute("ALTER TABLE announcements ADD COLUMN message TEXT")
        cols.append("message")
    if "body" not in cols:
        cur.execute("ALTER TABLE announcements ADD COLUMN body TEXT")
        cols.append("body")

    con.commit()
    con.close()


def add_announcement(message: str, created_by_role: str):
    msg = (message or "").strip()
    if not msg:
        return
    ensure_announcements_schema()

    con = db_conn()
    cur = con.cursor()
    cols = _table_cols(con, "announcements")

    if "body" in cols:
        cur.execute(
            "INSERT INTO announcements (created_at, created_by_role, message, body) VALUES (?, ?, ?, ?)",
            (now_ts(), str(created_by_role), msg, msg)
        )
    else:
        cur.execute(
            "INSERT INTO announcements (created_at, created_by_role, message) VALUES (?, ?, ?)",
            (now_ts(), str(created_by_role), msg)
        )
    con.commit()
    con.close()


def get_latest_announcements(limit: int = 10) -> pd.DataFrame:
    ensure_announcements_schema()
    con = db_conn()
    df = pd.read_sql_query(
        """
        SELECT id, created_at, created_by_role, COALESCE(message, body) AS message
        FROM announcements
        ORDER BY id DESC
        LIMIT ?
        """,
        con,
        params=(int(limit),)
    )
    con.close()
    return df


def delete_announcement(ann_id: int):
    con = db_conn()
    cur = con.cursor()
    cur.execute("DELETE FROM announcements WHERE id = ?", (int(ann_id),))
    con.commit()
    con.close()


def upsert_driver(driver_id: int, driver_name: str | None = None):
    con = db_conn()
    cur = con.cursor()
    cur.execute("SELECT driver_id, driver_name FROM drivers WHERE driver_id = ?", (int(driver_id),))
    row = cur.fetchone()

    if row is None:
        cur.execute(
            "INSERT INTO drivers (driver_id, driver_name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (int(driver_id), (driver_name or "").strip(), now_ts(), now_ts())
        )
    else:
        existing_name = (row[1] or "").strip()
        new_name = existing_name if not (driver_name and str(driver_name).strip()) else str(driver_name).strip()
        cur.execute(
            "UPDATE drivers SET driver_name=?, updated_at=? WHERE driver_id=?",
            (new_name, now_ts(), int(driver_id))
        )

    con.commit()
    con.close()


def get_hr_registry() -> pd.DataFrame:
    con = db_conn()
    df = pd.read_sql_query(
        """
        SELECT
            d.driver_id AS معرف_السائق,
            d.driver_name AS اسم_السائق,
            d.status AS الحالة,
            d.created_at AS تاريخ_الإضافة
        FROM drivers d
        ORDER BY d.driver_id
        """,
        con
    )
    con.close()
    return df
