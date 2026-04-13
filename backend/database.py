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
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at           TEXT NOT NULL,
                jd_position          TEXT,
                jd_domain            TEXT,
                total_resumes        INTEGER,
                filtered_out_count   INTEGER,
                analyzed_count       INTEGER,
                top_candidate_name   TEXT,
                top_candidate_score  INTEGER,
                result_json          TEXT NOT NULL
            )
        """)
        # 기존 DB에 컬럼 추가 (이미 있으면 무시)
        for col, typedef in [
            ("top_candidate_name", "TEXT"),
            ("top_candidate_score", "INTEGER"),
        ]:
            try:
                conn.execute(f"ALTER TABLE analyses ADD COLUMN {col} {typedef}")
            except sqlite3.OperationalError:
                pass


def save_analysis(result: dict) -> int:
    jd = result.get("jd_requirements", {})
    # 최고 점수 후보자 추출
    top_name = None
    top_score = None
    passed = [r for r in result.get("results", []) if r.get("filter_result", {}).get("passed") and r.get("match_result")]
    if passed:
        top = max(passed, key=lambda r: r["match_result"].get("total_score", 0))
        p = top.get("profile", {})
        top_name = p.get("name") or p.get("filename")
        top_score = top["match_result"].get("total_score")

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """INSERT INTO analyses
               (created_at, jd_position, jd_domain, total_resumes, filtered_out_count, analyzed_count,
                top_candidate_name, top_candidate_score, result_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                jd.get("position", ""),
                jd.get("domain", ""),
                result.get("total_resumes", 0),
                result.get("filtered_out_count", 0),
                result.get("analyzed_count", 0),
                top_name,
                top_score,
                json.dumps(result, ensure_ascii=False),
            ),
        )
        return cursor.lastrowid


def get_history(limit: int = 50) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT id, created_at, jd_position, jd_domain,
                      total_resumes, filtered_out_count, analyzed_count,
                      top_candidate_name, top_candidate_score
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
