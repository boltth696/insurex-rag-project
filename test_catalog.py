import hashlib
import json
import subprocess
import sys
from pathlib import Path
import pytest
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from insurex.catalog import load_catalog, verify_catalog_evidence, catalog_intent
from insurex.config import ROOT, Settings
from insurex.ingestion import load_pages
from insurex.graph import build_graph


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def test_reviewed_catalog_matches_actual_pdf_pages(catalog):
    pages, _ = load_pages(Settings().pdf_dir)
    assert verify_catalog_evidence(catalog, pages)
    by_id = {p.id: p for p in catalog.products}
    assert len(by_id) == 5
    assert by_id["aomsook"].coverage_kind == "years"
    assert by_id["aomsook"].coverage_value == 25
    assert by_id["aomsook"].variants[0].payment_years == 15
    assert by_id["cheeva"].coverage_value == 90
    assert by_id["cheeva"].variants[0].payment_years == 10
    assert [v.payment_years for v in by_id["ci_plus"].variants] == [5,10,20]
    assert [v.payment_until_age for v in by_id["bamnan"].variants] == [55,60,65]
    assert by_id["raksa"].name_th == "คุ้มรักษา เหมาจ่าย เอ็กซ์ตร้า"
    assert by_id["raksa"].payment_kind == "not_fixed"


@pytest.mark.parametrize("question", ["what products are there to choose from", "What insurance plans are available?", "List all products", "Which policies do you offer?", "มีผลิตภัณฑ์อะไรให้เลือกบ้าง"])
def test_actual_product_questions_answer_all_five_without_model(catalog, question):
    graph = build_graph(None, None, catalog=catalog)
    state = graph.invoke({"messages": [HumanMessage(content=question)]})
    assert state["mode"] == "catalog_list"
    assert state["error"] == ""
    text = state["messages"][-1].content
    for p in catalog.products:
        assert p.name_th in text
        assert p.source_file in text
    assert "คุ้มรักษามะเร็ง" not in text
    assert "details are limited" not in text


def test_exact_failed_question_returns_correct_five_year_winner(catalog):
    q = "for all of the policies which is the one that i'd have to pay the shortest amount of years in premimum"
    state = build_graph(None, None, catalog=catalog).invoke({"messages": [HumanMessage(content=q)]})
    text = state["messages"][-1].content
    assert state["error"] == ""
    assert "90/5: 5 years" in text.splitlines()[0]
    assert "คุ้มตลอดชีพ ซีไอ พลัส" in text.splitlines()[0]
    assert "coverage" in text.lower()
    assert "Coverage: 25 years" in text
    assert "Premium payments: 15 years" in text
    assert "Pension payment durations depend on your entry age" in text


def test_catalog_longest_and_named_product_rank(catalog):
    graph = build_graph(None, None, catalog=catalog)
    longest = graph.invoke({"messages": [HumanMessage(content="Which policy has the longest premium-payment period?")]})
    assert "90/20: 20 years" in longest["messages"][-1].content.splitlines()[0]
    savings = graph.invoke({"messages": [HumanMessage(content="What is the shortest premium payment period for Aomsook?")]})
    assert "25/15: 15 years" in savings["messages"][-1].content.splitlines()[0]
    pension = graph.invoke({"messages": [HumanMessage(content="What is the shortest premium payment period for pension?")]})
    assert "requires your entry age" in pension["messages"][-1].content


def test_named_savings_fact_does_not_reverse_fields(catalog):
    state = build_graph(None, None, catalog=catalog).invoke({"messages": [HumanMessage(content="How many years do I pay premiums for Khum Aomsook 25/15?")]})
    text = state["messages"][-1].content
    assert state["mode"] == "catalog_fact"
    assert "Coverage: 25 years" in text
    assert "Premium payments: 15 years" in text
    assert "Coverage: 15 years" not in text
    assert "Premium payments: 25 years" not in text


def test_ambiguous_plan_code_requests_product_name(catalog):
    state = build_graph(None, None, catalog=catalog).invoke({"messages": [HumanMessage(content="How many years do I pay for 90/10?")]})
    assert "Please specify the product name" in state["messages"][-1].content


def test_details_are_not_mistaken_for_catalog_list(catalog):
    for question in ["Which products cover pregnancy?", "What exclusions does Cheeva have?", "What does Cheeva cover?"]:
        assert catalog_intent(question, catalog) is None
    state = build_graph(None, None, catalog=catalog).invoke({"messages": [HumanMessage(content="What exclusions does Cheeva have?")]})
    assert "Detailed benefits or exclusions require" in state["messages"][-1].content


def test_old_wrong_answers_do_not_affect_new_catalog_answers(catalog, tmp_path):
    config = {"configurable": {"thread_id": "old-session"}}
    with SqliteSaver.from_conn_string(str(tmp_path / "sessions.sqlite")) as saver:
        graph = build_graph(None, None, catalog=catalog, checkpointer=saver)
        graph.update_state(config, {"messages": [HumanMessage(content="old question"), AIMessage(content="คุ้มออมสุข: coverage 15 years, premiums 25 years")], "mode": "payment_rank", "error": "old comparison error"})
        state = graph.invoke({"messages": [HumanMessage(content="what products are there to choose from")]}, config)
        assert state["error"] == ""
        assert "The supplied brochures describe these 5 product families" in state["messages"][-1].content
        assert "Coverage: 25 years" in state["messages"][-1].content
        hello = graph.invoke({"messages": [HumanMessage(content="hello")]}, config)
        assert hello["messages"][-1].content.startswith("Hello!")


def test_changed_pdf_is_rejected(catalog, tmp_path):
    folder = tmp_path / "pdfs"
    folder.mkdir()
    for p in catalog.products:
        (folder / p.source_file).write_bytes(b"changed brochure")
    with pytest.raises(ValueError, match="PDF changed"):
        load_catalog(pdf_dir=folder)


def test_added_product_requires_catalog_review(catalog, tmp_path):
    folder = tmp_path / "pdfs"
    folder.mkdir()
    for p in catalog.products:
        (folder / p.source_file).write_bytes(b"brochure")
    (folder / "new_product.pdf").write_bytes(b"new")
    with pytest.raises(ValueError, match="cover each"):
        load_catalog(pdf_dir=folder)


def test_actual_cli_offline_dialogue(tmp_path):
    # Actual production CLI and graph, not model-simulated catalog replies.
    result = subprocess.run([sys.executable, "-m", "insurex.cli", "chat", "--offline", "--session", "catalog-regression", "--storage-dir", str(tmp_path/'demo-storage')], input="what products are there to choose from\nfor all of the policies which is the one that i'd have to pay the shortest amount of years in premimum\nhello\n/exit\n", text=True, encoding="utf-8", capture_output=True, cwd=ROOT, env={**__import__('os').environ,"PYTHONIOENCODING":"utf-8"}, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "The supplied brochures describe these 5 product families" in result.stdout
    assert "90/5: 5 years" in result.stdout
    assert "Assistant: Hello!" in result.stdout
    assert "Comparison validation failed" not in result.stdout
