import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class Settings:
    pdf_dir: Path = ROOT / "data" / "pdfs"
    index_dir: Path = ROOT / "storage" / "faiss"
    session_db: Path = ROOT / "storage" / "sessions.sqlite"
    lead_db: Path = ROOT / "storage" / "leads.sqlite"
    chat_model: str = "gpt-4.1-mini"
    embedding_model: str = "text-embedding-3-small"
    top_k: int = 5
    chunk_size: int = 1000
    chunk_overlap: int = 150

    @classmethod
    def load(cls):
        load_dotenv(ROOT / ".env", override=False)
        settings = cls(
            chat_model=os.getenv("CHAT_MODEL", "gpt-4.1-mini"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            top_k=int(os.getenv("TOP_K", "5")),
            chunk_size=int(os.getenv("CHUNK_SIZE", "1000")),
            chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "150")),
        )
        if settings.top_k < 1 or not 0 <= settings.chunk_overlap < settings.chunk_size:
            raise ValueError("TOP_K must be positive and 0 <= CHUNK_OVERLAP < CHUNK_SIZE.")
        return settings


def require_api_key():
    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise ValueError("Add OPENAI_API_KEY to .env before ingesting or chatting.")
