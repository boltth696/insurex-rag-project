"""Read local lead records without loading model or retrieval libraries."""
import json
import sqlite3
from contextlib import closing
from pathlib import Path


def read_leads(database_path, session_id=None):
    path = Path(database_path).resolve()
    if not path.exists():
        return []
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='leads'").fetchone():
            return []
        if session_id is None:
            rows = connection.execute("SELECT structured_json FROM leads ORDER BY created_at,session_id,lead_id").fetchall()
        else:
            rows = connection.execute("SELECT structured_json FROM leads WHERE session_id=? ORDER BY created_at,lead_id", (session_id,)).fetchall()
    return [json.loads(row[0]) for row in rows]
