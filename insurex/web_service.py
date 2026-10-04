"""Local browser adapter using the same graph and databases as the CLI."""
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from threading import RLock
import os

from .config import Settings, require_api_key
from .sessions import list_sessions


def web_settings():
    settings = Settings.load()
    # Test/demo launches can use separate storage without copying the index.
    directory = os.getenv("INSUREX_UI_STORAGE_DIR", "").strip()
    if directory:
        root = Path(directory).resolve()
        settings = replace(settings, session_db=root / "sessions.sqlite", lead_db=root / "leads.sqlite")
    return settings


class ChatService:
    def __init__(self, settings, offline=False):
        from .catalog import load_catalog
        self.settings = settings
        self.offline = offline
        self.catalog = load_catalog(pdf_dir=settings.pdf_dir)
        self.store = self.model = None
        self.lock = RLock()
        if not offline:
            require_api_key()
            from .vectorstore import load_index
            from langchain_openai import ChatOpenAI
            self.store = load_index(settings)
            self.model = ChatOpenAI(model=settings.chat_model, temperature=0, timeout=60, max_retries=2)

    @contextmanager
    def graph(self):
        from langgraph.checkpoint.sqlite import SqliteSaver
        from .graph import build_graph
        from .leads import create_lead_tool
        self.settings.session_db.parent.mkdir(parents=True, exist_ok=True)
        # SQLite connections belong to this request, never a cached global saver.
        with self.lock, SqliteSaver.from_conn_string(str(self.settings.session_db)) as saver:
            yield build_graph(self.store, self.model, self.settings.top_k, saver,
                              catalog=self.catalog,
                              lead_tool=None if self.offline else create_lead_tool(self.settings.lead_db))

    @staticmethod
    def config(session_id):
        if not isinstance(session_id, str) or not session_id.strip() or len(session_id) > 200:
            raise ValueError("Choose a conversation ID between 1 and 200 characters.")
        return {"configurable": {"thread_id": session_id}}

    def sessions(self):
        return list_sessions(self.settings.session_db)

    def history(self, session_id):
        with self.graph() as graph:
            return graph.get_state(self.config(session_id)).values

    def send(self, session_id, question):
        from langchain_core.messages import HumanMessage
        question = question.strip()
        if not question or len(question) > 6000:
            raise ValueError("Please enter a message of up to 6,000 characters.")
        if question.lower() == "/exit":
            raise ValueError("Use New conversation to start again, or close the browser tab.")
        with self.graph() as graph:
            return graph.invoke({"messages": [HumanMessage(content=question)]}, self.config(session_id))


def visible_messages(state):
    """Show human/assistant text only; omit tool messages and internal metadata."""
    return [("user" if m.type == "human" else "assistant", str(m.content))
            for m in state.get("messages", []) if m.type in ("human", "ai") and m.content]
