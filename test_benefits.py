"""Offline checks of real indexed evidence; model stubs do not prove live accuracy."""
import json
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from insurex.config import ROOT
from insurex.catalog import load_catalog
from insurex.comparison import page_evidence
from insurex.benefits import benefit_notes
from insurex.graph import build_graph, GroundedAnswer
import pytest


QUESTION = "What is the difference between the critical illness protection in Khum Cheeva and Khum Talodcheep CI Plus?"


class IndexedStore:
    def __init__(self):
        folder = ROOT / "storage/faiss"
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        # This project's persisted JSON docstore is safe to inspect without embeddings.
        rows = json.loads((folder / manifest["documents_file"]).read_text(encoding="utf-8"))
        self.docs = {r["id"]: Document(page_content=r["text"], metadata=r["metadata"]) for r in rows}
        self.index_to_docstore_id = {r["position"]: r["id"] for r in rows}
        self.docstore = self

    def search(self, doc_id):
        return self.docs[doc_id]

    def similarity_search(self, *args, **kwargs):
        raise AssertionError("Named comparison must read all pages of both products")


class CaptureModel:
    def __init__(self, omit=False):
        self.calls = []
        self.omit = omit

    def with_structured_output(self, schema):
        return self

    def invoke(self, messages):
        self.calls.append(messages)
        return GroundedAnswer(supported=True, answer="A test comparison", citation_ids=[1] if self.omit else [2, 3, 4, 5, 6])


def test_named_ci_comparison_contains_both_complete_brochures_and_table_notes():
    catalog = load_catalog()
    model = CaptureModel()
    state = build_graph(IndexedStore(), model, catalog=catalog, top_k=1).invoke({"messages": [HumanMessage(content=QUESTION)]})
    assert len(state["sources"]) == 6
    assert {s["file"] for s in state["sources"]} == {p.source_file for p in catalog.products if p.id in ("cheeva", "ci_plus")}
    assert "THB 60,000" in state["context"]
    assert "THB 240,000" in state["context"]
    assert "before the policy anniversary at age 85" in state["context"]
    assert "does not enumerate the complete CI 50 illness definitions" in state["context"]
    assert "eligible total premiums paid" in state["context"]
    assert "policy terminates" in state["context"]
    assert "90-day waiting period" in state["context"]
    assert "Sources:" in state["messages"][-1].content
    assert any("Read all supplied pages" in str(m.content) for m in model.calls[0])


def test_comparison_cannot_claim_support_with_only_one_product_cited():
    model = CaptureModel(omit=True)
    state = build_graph(IndexedStore(), model, catalog=load_catalog()).invoke({"messages": [HumanMessage(content=QUESTION)]})
    assert len(model.calls) == 2
    assert "could not find enough" in state["messages"][-1].content
    assert "Sources:" not in state["messages"][-1].content


def test_reviewed_notes_are_bound_to_real_indexed_pages():
    catalog = load_catalog()
    store = IndexedStore()
    notes = [benefit_notes(catalog, d) for d in page_evidence(list(store.docs.values()))]
    assert all(any(benefit_notes(catalog, d) for d in page_evidence(list(store.docs.values())) if d.metadata['source'] == p.source_file) for p in catalog.products)
    cheeva = next(p for p in catalog.products if p.id == "cheeva")
    with pytest.raises(ValueError, match="missing its source-page evidence"):
        benefit_notes(catalog, Document(page_content="unrelated", metadata={"source": cheeva.source_file, "page": 2}))


def test_single_named_benefit_question_reads_table_and_conditions():
    state = build_graph(IndexedStore(), CaptureModel(), catalog=load_catalog(), top_k=1).invoke({"messages": [HumanMessage(content="What critical illness benefits does Khum Cheeva cover?")]})
    assert len(state["sources"]) == 3
    assert "THB 60,000" in state["context"]
    assert "CI Plus integrates" not in state["context"]


def test_missing_comparison_citation_can_be_corrected_on_retry():
    class RecoverModel(CaptureModel):
        def invoke(self, messages):
            self.omit = not self.calls
            return super().invoke(messages)
    model = RecoverModel()
    state = build_graph(IndexedStore(), model, catalog=load_catalog()).invoke({"messages": [HumanMessage(content=QUESTION)]})
    assert len(model.calls) == 2
    assert "Sources:" in state["messages"][-1].content
