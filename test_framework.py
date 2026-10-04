from dataclasses import replace
import hashlib
import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage, HumanMessage
from langchain_community.vectorstores import FAISS
from langgraph.checkpoint.sqlite import SqliteSaver
from insurex.config import Settings
from insurex.ingestion import load_pages, split_pages
from insurex.vectorstore import save_index, load_index
from insurex.graph import build_graph, GroundedAnswer


class OfflineEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [self.embed_query(t) for t in texts]
    def embed_query(self, text):
        # Deterministic test vectors only. Not suitable for semantic retrieval.
        digest = hashlib.sha256(text.encode()).digest()
        return [float(x) for x in digest[:16]]


class StubModel:
    def __init__(self, supported=True, fail=False, citation_ids=None):
        self.supported = supported
        self.fail = fail
        self.citation_ids = [1] if citation_ids is None else citation_ids
    def with_structured_output(self, schema):
        return self
    def invoke(self, messages):
        if self.fail:
            raise RuntimeError("simulated failure")
        if "Rewrite the latest" in messages[0].content:
            return AIMessage(content=messages[-1].content)
        return GroundedAnswer(supported=self.supported, answer="Supported test answer" if self.supported else "Please specify the product.", citation_ids=self.citation_ids)


def store():
    return FAISS.from_documents([
        Document(page_content="Example coverage", metadata={"source": "example.pdf", "page": 2}),
        Document(page_content="Example exclusion", metadata={"source": "example.pdf", "page": 3}),
    ], OfflineEmbeddings(), normalize_L2=True)


def test_all_five_pdfs_extract_and_chunk():
    settings = Settings()
    pages, report = load_pages(settings.pdf_dir)
    assert len(report) == 5
    assert all(p["characters"] > 30 for item in report for p in item["pages"])
    assert all(sum(p["thai_characters"] for p in item["pages"]) > 100 for item in report)
    chunks = split_pages(pages, settings)
    assert chunks
    assert all(c.metadata["source"].endswith(".pdf") and c.metadata["page"] >= 1 for c in chunks)


def test_faiss_json_roundtrip_and_model_mismatch(tmp_path):
    settings = replace(Settings(), index_dir=tmp_path, embedding_model="offline-test")
    original = store()
    save_index(original, tmp_path, {"embedding_model": "offline-test"})
    loaded = load_index(settings, OfflineEmbeddings())
    assert loaded.similarity_search("Example coverage", k=1)[0].page_content == "Example coverage"
    assert not list(tmp_path.glob("*.pkl"))
    with pytest.raises(ValueError, match="changed"):
        load_index(replace(settings, embedding_model="other"), OfflineEmbeddings())


def test_grounded_response_cites_page():
    graph = build_graph(store(), StubModel())
    result = graph.invoke({"messages": [HumanMessage(content="coverage?")]})
    assert "example.pdf, page" in result["messages"][-1].content


def test_unsupported_response():
    graph = build_graph(store(), StubModel(supported=False, citation_ids=[]))
    result = graph.invoke({"messages": [HumanMessage(content="unknown product?")]})
    assert result["messages"][-1].content == "Please specify the product."


def test_invalid_citations_are_rejected():
    graph = build_graph(store(), StubModel(citation_ids=[999]))
    result = graph.invoke({"messages": [HumanMessage(content="coverage?")]})
    assert "could not find enough" in result["messages"][-1].content


def test_retrieval_error_does_not_reuse_context():
    class BrokenStore:
        def similarity_search(self, *args, **kwargs):
            raise RuntimeError("offline")
    graph = build_graph(BrokenStore(), StubModel())
    result = graph.invoke({"messages": [HumanMessage(content="coverage?")], "context": "stale evidence"})
    assert result["context"] == ""
    assert "search is unavailable" in result["messages"][-1].content


def test_generation_failure():
    graph = build_graph(store(), StubModel(fail=True))
    result = graph.invoke({"messages": [HumanMessage(content="coverage?")]})
    assert "answer service is unavailable" in result["messages"][-1].content


def test_sessions_are_isolated_and_restore_after_restart(tmp_path):
    db = str(tmp_path / "sessions.sqlite")
    config_a = {"configurable": {"thread_id": "alice"}}
    config_b = {"configurable": {"thread_id": "bob"}}
    with SqliteSaver.from_conn_string(db) as saver:
        graph = build_graph(store(), StubModel(), checkpointer=saver)
        graph.invoke({"messages": [HumanMessage(content="alice question")]}, config_a)
        graph.invoke({"messages": [HumanMessage(content="bob question")]}, config_b)
        assert "alice question" not in [m.content for m in graph.get_state(config_b).values["messages"]]
    with SqliteSaver.from_conn_string(db) as saver:
        restored = build_graph(store(), StubModel(), checkpointer=saver)
        assert restored.get_state(config_a).values["messages"][0].content == "alice question"
        result = restored.invoke({"messages": [HumanMessage(content="follow-up")]}, config_a)
        assert len(result["messages"]) == 4


def test_legacy_thai_normalization():
    from insurex.ingestion import normalize_thai
    assert normalize_thai("คุ\uf70bมครอง เป\uf712น ปกป\uf706อง") == "คุ้มครอง เป็น ปกป้อง"
    pages, _ = load_pages(Settings().pdf_dir)
    assert not any(0xF700 <= ord(c) <= 0xF71A for page in pages for c in page.page_content)
