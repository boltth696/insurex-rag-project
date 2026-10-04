import pytest
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage
from langchain_community.vectorstores import FAISS
from insurex.comparison import PaymentTerm, PaymentComparison, comparison_intent, response_language, validate_terms, render_comparison
from insurex.graph import build_graph, GroundedAnswer
from tests.test_framework import OfflineEmbeddings

QUESTION = "for all of the policies which is the one that i'd have to pay the shortest amount of years in premimum"


def fixture():
    docs = [
        Document(page_content="Payment period: 15 years.", metadata={"source": "savings.pdf", "page": 2}),
        Document(page_content="Payment period: 10 years.", metadata={"source": "life.pdf", "page": 3}),
        Document(page_content="Payment options: 5 years, 10 years or 20 years.", metadata={"source": "ci.pdf", "page": 1}),
        Document(page_content="Pay premiums until age 55. Example: age 45, pays for 10 years.", metadata={"source": "pension.pdf", "page": 4}),
        Document(page_content="This is an annual renewable health rider.", metadata={"source": "health.pdf", "page": 4}),
    ]
    terms = [
        PaymentTerm(source_file="savings.pdf", product="Savings", kind="fixed", years=[15], citation_id=1, evidence_quote=docs[0].page_content),
        PaymentTerm(source_file="life.pdf", product="Life", kind="fixed", years=[10], citation_id=2, evidence_quote=docs[1].page_content),
        PaymentTerm(source_file="ci.pdf", product="CI 90/5, 90/10, 90/20", kind="fixed", years=[5,10,20], citation_id=3, evidence_quote=docs[2].page_content),
        PaymentTerm(source_file="pension.pdf", product="Pension", kind="age_based", years=[], citation_id=4, evidence_quote="Pay premiums until age 55."),
        PaymentTerm(source_file="health.pdf", product="Health rider", kind="renewable", years=[], citation_id=5, evidence_quote=docs[4].page_content),
    ]
    return docs, PaymentComparison(terms=terms)


class ComparisonModel:
    def __init__(self, response):
        self.response = response
        self.prompts = []
    def with_structured_output(self, schema):
        return self
    def invoke(self, messages):
        self.prompts.append(messages)
        return self.response


def test_original_question_gets_global_payment_route():
    assert comparison_intent(QUESTION) == "payment_rank"
    assert comparison_intent("Which plan requires the fewest years of premium payments?") == "payment_rank"
    assert comparison_intent("แผนไหนจ่ายเบี้ยสั้นที่สุด") == "payment_rank"
    assert comparison_intent("Compare exclusions across all plans") == "all_products"
    assert comparison_intent("What does Cheeva cover?") == "single"


def test_minimum_is_calculated_not_chosen_by_model():
    docs, result = fixture()
    terms = validate_terms(result, docs)
    text = render_comparison(terms, docs, "English", QUESTION)
    assert text.splitlines()[0].endswith(": 5 years.")
    assert "CI 90/5" in text.splitlines()[0]
    assert "15 years" in text
    assert "Depends on entry age" in text
    assert "a worked example is not a universal" in text
    assert "Renewable rider" in text
    assert "ci.pdf, page 1" in text


def test_global_retrieval_covers_all_products_even_when_top_k_is_one():
    docs, result = fixture()
    store = FAISS.from_documents(docs, OfflineEmbeddings())
    model = ComparisonModel(result)
    graph = build_graph(store, model, top_k=1)
    state = graph.invoke({"messages": [HumanMessage(content=QUESTION)]})
    assert len(state["evidence"]) == 5
    assert state["error"] == ""
    assert state["messages"][-1].content.startswith("The shortest")


@pytest.mark.parametrize("corruption", ["missing_product", "wrong_quote", "wrong_year", "wrong_source"])
def test_unverified_comparisons_are_rejected(corruption):
    docs, result = fixture()
    if corruption == "missing_product":
        result.terms.pop()
    elif corruption == "wrong_quote":
        result.terms[0].evidence_quote = "Pay 3 years."
    elif corruption == "wrong_year":
        result.terms[0].years = [3]
    else:
        result.terms[0].citation_id = 2
    with pytest.raises(ValueError):
        validate_terms(result, docs)
    graph = build_graph(FAISS.from_documents(docs, OfflineEmbeddings()), ComparisonModel(result))
    state = graph.invoke({"messages": [HumanMessage(content=QUESTION)]})
    assert "cannot safely rank" in state["messages"][-1].content


def test_language_uses_latest_question_not_thai_history():
    docs, result = fixture()
    graph = build_graph(FAISS.from_documents(docs, OfflineEmbeddings()), ComparisonModel(result))
    state = graph.invoke({"messages": [HumanMessage(content="ถามภาษาไทย"), AIMessage(content="15 ปีสั้นที่สุด"), HumanMessage(content=QUESTION)]})
    assert state["language"] == "English"
    assert state["messages"][-1].content.startswith("The shortest")
    assert response_language("What does แผนคุ้มชีวา cover?") == "English"
    assert response_language("แผนไหนจ่ายเบี้ยสั้นที่สุด") == "Thai"


def test_longest_period_uses_maximum():
    docs, result = fixture()
    text = render_comparison(result.terms, docs, "English", "Which plan has the longest premium-payment period?")
    assert text.splitlines()[0].endswith(": 20 years.")


def test_general_comparison_receives_every_pdf_and_english_instruction():
    docs, _ = fixture()
    model = ComparisonModel(GroundedAnswer(supported=True, answer="English comparison", citation_ids=[1,2,3,4,5]))
    graph = build_graph(FAISS.from_documents(docs, OfflineEmbeddings()), model, top_k=1)
    state = graph.invoke({"messages": [HumanMessage(content="Compare all policies")]})
    assert len(state["evidence"]) == 5
    assert "REQUIRED RESPONSE LANGUAGE: English" in model.prompts[0][0].content


def test_equivalent_thai_unicode_quotes():
    from insurex.comparison import quote_key
    assert quote_key("ชำระเบี้ย 10 ปี") == quote_key("ช\u0e4dาระเบี้ย\n10 ปี")
    doc = Document(page_content="ระยะเวลาช\u0e4dาระเบี้ย 10 ปี", metadata={"source": "thai.pdf", "page": 1})
    term = PaymentTerm(source_file="thai.pdf", product="Thai plan", kind="fixed", years=[10], citation_id=1, evidence_quote="ระยะเวลาชำระเบี้ย 10 ปี")
    assert validate_terms(PaymentComparison(terms=[term]), [doc])


def test_page_reassembly_preserves_quote_across_chunk_boundary():
    from insurex.comparison import page_evidence
    common = "Premium payment duration: "
    chunks = [Document(page_content="Product description. " + common, metadata={"source": "a.pdf", "page": 1}), Document(page_content=common + "5 years.", metadata={"source": "a.pdf", "page": 1})]
    pages = page_evidence(chunks)
    assert len(pages) == 1
    assert pages[0].page_content.count(common) == 1
    assert "Premium payment duration: 5 years." in pages[0].page_content


def test_quote_on_another_page_of_same_pdf_corrects_citation():
    docs, result = fixture()
    docs.append(Document(page_content="Other text from the savings plan.", metadata={"source": "savings.pdf", "page": 1}))
    result.terms[0].citation_id = 6
    terms = validate_terms(result, docs)
    assert terms[0].citation_id == 1


def test_invalid_extraction_retries_once_and_recovers():
    docs, good = fixture()
    _, bad = fixture()
    bad.terms[0].evidence_quote = "invented words"
    class RetryModel(ComparisonModel):
        def invoke(self, messages):
            self.prompts.append(list(messages))
            return bad if len(self.prompts) == 1 else good
    model = RetryModel(good)
    state = build_graph(FAISS.from_documents(docs, OfflineEmbeddings()), model).invoke({"messages": [HumanMessage(content=QUESTION)]})
    assert len(model.prompts) == 2
    assert state["error"] == ""
    assert state["messages"][-1].content.startswith("The shortest")
    assert "Validation rejected" in model.prompts[1][-1].content


def test_bad_quote_retry_is_bounded():
    docs, result = fixture()
    result.terms[0].evidence_quote = "invented words"
    model = ComparisonModel(result)
    state = build_graph(FAISS.from_documents(docs, OfflineEmbeddings()), model).invoke({"messages": [HumanMessage(content=QUESTION)]})
    assert len(model.prompts) == 2
    assert "cannot safely rank" in state["messages"][-1].content


def test_health_rider_missing_quote_does_not_block_verified_fixed_plans():
    docs, result = fixture()
    result.terms[4].evidence_quote = "The rider requires annual payments until age 99."
    terms = validate_terms(result, docs)
    assert terms[4].kind == "unspecified"
    assert terms[4].evidence_quote == ""
    text = render_comparison(terms, docs, "English", QUESTION)
    assert text.splitlines()[0].endswith(": 5 years.")
    assert "excluded from the ranking" in text
    assert "Renewable rider" not in text
    assert "until age 99" not in text


def test_unspecified_payment_period_needs_no_invented_quote():
    docs, result = fixture()
    result.terms[4].kind = "unspecified"
    result.terms[4].evidence_quote = ""
    graph = build_graph(FAISS.from_documents(docs, OfflineEmbeddings()), ComparisonModel(result))
    state = graph.invoke({"messages": [HumanMessage(content=QUESTION)]})
    assert state["error"] == ""
    assert state["messages"][-1].content.startswith("The shortest")


def test_unsupported_pension_claim_is_removed():
    docs, result = fixture()
    result.terms[3].evidence_quote = "Every pension customer pays exactly 10 years."
    terms = validate_terms(result, docs)
    assert terms[3].kind == "unspecified"
    assert terms[3].years == []


def test_unverified_kind_cannot_hide_a_numeric_payment_claim():
    docs, result = fixture()
    result.terms[4].kind = "unspecified"
    result.terms[4].years = [1]
    with pytest.raises(ValueError, match="Non-fixed"):
        validate_terms(result, docs)


@pytest.mark.parametrize("greeting,language", [("hello", "English"), ("Hi!", "English"), ("สวัสดีครับ", "Thai")])
def test_greeting_after_failed_comparison_does_not_search_or_call_model(greeting, language, tmp_path):
    from langgraph.checkpoint.sqlite import SqliteSaver
    docs, result = fixture()
    result.terms[0].evidence_quote = "invalid quote"
    model = ComparisonModel(result)
    store = FAISS.from_documents(docs, OfflineEmbeddings())
    config = {"configurable": {"thread_id": "same-session"}}
    with SqliteSaver.from_conn_string(str(tmp_path / "sessions.sqlite")) as saver:
        graph = build_graph(store, model, checkpointer=saver)
        failed = graph.invoke({"messages": [HumanMessage(content=QUESTION)]}, config)
        assert "cannot safely rank" in failed["messages"][-1].content
        calls = len(model.prompts)
        state = graph.invoke({"messages": [HumanMessage(content=greeting)]}, config)
        assert state["mode"] == "greeting"
        assert state["language"] == language
        assert state["error"] == ""
        assert state["context"] == ""
        assert state["sources"] == []
        assert len(model.prompts) == calls
        assert "cannot safely rank" not in state["messages"][-1].content
        assert len(state["messages"]) == 4


def test_greeting_prefix_does_not_hide_an_insurance_question():
    assert comparison_intent("Hello, which plan has the shortest premium-payment period?") == "payment_rank"
