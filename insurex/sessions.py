"""Read saved conversation IDs without loading their messages."""
import sqlite3
from contextlib import closing
from pathlib import Path


def list_sessions(database_path):
    path = Path(database_path).resolve()
    if not path.exists():
        return []
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='checkpoints'").fetchone():
            return []
        return [row[0] for row in connection.execute("SELECT DISTINCT thread_id FROM checkpoints ORDER BY thread_id")]
