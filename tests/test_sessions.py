import sqlite3
from insurex.sessions import list_sessions


def test_missing_database_does_not_create_file(tmp_path):
    path = tmp_path / "sessions.sqlite"
    assert list_sessions(path) == []
    assert not path.exists()


def test_distinct_conversations_not_checkpoint_count(tmp_path):
    path = tmp_path / "sessions.sqlite"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE checkpoints(thread_id TEXT,checkpoint_id TEXT)")
        conn.executemany("INSERT INTO checkpoints VALUES (?,?)", [("b", "1"), ("a", "2"), ("b", "3")])
    assert list_sessions(path) == ["a", "b"]


def test_empty_uninitialized_database(tmp_path):
    path = tmp_path / "sessions.sqlite"
    sqlite3.connect(path).close()
    assert list_sessions(path) == []
