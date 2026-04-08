import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "analyses.db"


def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at         TEXT NOT NULL,
                jd_position        TEXT,
                jd_domain          TEXT,
                total_resumes      INTEGER,
                filtered_out_count INTEGER,
                analyzed_count     INTEGER,
                result_json        TEXT NOT NULL
            )
        """)


def save_analysis(result: dict) -> int:
    jd = result.get("jd_requirements", {})
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """INSERT INTO analyses
               (created_at, jd_position, jd_domain, total_resumes, filtered_out_count, analyzed_count, result_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                jd.get("position", ""),
                jd.get("domain", ""),
                result.get("total_resumes", 0),
                result.get("filtered_out_count", 0),
                result.get("analyzed_count", 0),
                json.dumps(result, ensure_ascii=False),
            ),
        )
        return cursor.lastrowid


def get_history(limit: int = 50) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT id, created_at, jd_position, jd_domain,
                      total_resumes, filtered_out_count, analyzed_count
               FROM analyses
               ORDER BY created_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_analysis(analysis_id: int) -> dict | None:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT result_json FROM analyses WHERE id = ?", (analysis_id,)
        ).fetchone()
        return json.loads(row[0]) if row else None


def delete_analysis(analysis_id: int) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
        return cursor.rowcount > 0
