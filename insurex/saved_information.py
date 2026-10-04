"""Read the instance's latest local checkpoint without model/index initialization."""
from contextlib import closing
from pathlib import Path
import sqlite3


def read_saved_session(database_path, session_id):
    path = Path(database_path).resolve()
    if not path.exists():
        return {}
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='checkpoints'").fetchone():
            return {}
        row = connection.execute(
            "SELECT type, checkpoint FROM checkpoints WHERE thread_id=? AND checkpoint_ns='' ORDER BY checkpoint_id DESC LIMIT 1",
            (session_id,),
        ).fetchone()
    if row is None:
        return {}
    # This is the serializer used by the pinned SQLite checkpoint saver.
    # Read only app-owned databases; pickle fallback remains disabled.
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
    checkpoint = JsonPlusSerializer(pickle_fallback=False).loads_typed((row[0], row[1]))
    values = checkpoint.get("channel_values", {})
    if not isinstance(values, dict):
        raise ValueError("Saved conversation has an invalid state.")
    return values


def remembered_details(state):
    profile = state.get("customer_profile", {})
    fields = {"age_quote":"Age", "budget_quote":"Premium budget", "goal_quote":"Current goal",
              "benefit_quote":"Requested benefit", "existing_coverage_quote":"Existing insurance"}
    return [{"Detail":label,"Customer statement":profile[field]}
            for field,label in fields.items() if profile.get(field)]
