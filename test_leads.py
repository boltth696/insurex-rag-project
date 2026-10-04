import sqlite3
import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from insurex.catalog import load_catalog
from insurex.graph import build_graph, FollowupDecision, GroundedAnswer
from insurex.leads import LeadTurn, QuotedValue, LeadRecord, lead_interest_intent, merge_lead, create_lead_tool
from tests.test_benefits import IndexedStore

INTEREST = "I am interested in Khum Cheeva."
DETAILS = "My name is Demo Customer. I freelance. My income is 30000 THB per month."
PHONE = "My phone is 0812345678."


def fields(phone=None):
    return LeadTurn(product_id="cheeva", product_quote="Khum Cheeva", name=QuotedValue(value="Demo Customer", quote="My name is Demo Customer"), occupation=QuotedValue(value="freelance", quote="I freelance"), income=QuotedValue(value="30000 THB per month", quote="My income is 30000 THB per month"), contact_number=QuotedValue(value=phone, quote=f"My phone is {phone}") if phone else None)


class Model:
    def __init__(self, schema=None):
        self.schema = schema
    def with_structured_output(self, schema):
        return Model(schema)
    def invoke(self, messages):
        latest = next(m.content for m in reversed(messages) if isinstance(m, HumanMessage))
        if self.schema is FollowupDecision:
            if "sounds like" in latest:
                return FollowupDecision(kind="lead_interest", interest_quote=latest, query=latest)
            return FollowupDecision(kind="detail", query=latest)
        if self.schema is GroundedAnswer:
            return GroundedAnswer(supported=True, answer="Cheeva base coverage is until age 90.", citation_ids=[1])
        assert self.schema is LeadTurn
        if latest == INTEREST or "sounds like" in latest:
            return LeadTurn(product_id="cheeva", product_quote="Khum Cheeva")
        if "coverage" in latest:
            return LeadTurn(action="detail", query="Khum Cheeva coverage duration")
        if "phone" in latest:
            number = latest.split("is ")[1].rstrip(".")
            return LeadTurn(contact_number=QuotedValue(value=number, quote=latest.rstrip(".")))
        return fields()


@pytest.mark.parametrize("question", [INTEREST, "I'm interested in Khum Aomsook", "I want to buy Khum Cheeva", "สนใจคุ้มชีวา", "อยากซื้อคุ้มออมสุข"])
def test_interest_triggers(question):
    assert lead_interest_intent(question)


@pytest.mark.parametrize("question", ["What products are there?", "What are the benefits of Khum Cheeva?", "I am not interested in Khum Cheeva", "ไม่สนใจคุ้มชีวา"])
def test_questions_and_negated_interest_do_not_trigger(question):
    assert not lead_interest_intent(question)


def test_collection_survives_restart_and_saves_structured_record(tmp_path):
    session_db, leads_db = tmp_path / "sessions.sqlite", tmp_path / "leads.sqlite"
    tool = create_lead_tool(leads_db)
    config = {"configurable": {"thread_id": "demo"}}
    with SqliteSaver.from_conn_string(str(session_db)) as saver:
        graph = build_graph(IndexedStore(), Model(), catalog=load_catalog(), checkpointer=saver, lead_tool=tool)
        first = graph.invoke({"messages": [HumanMessage(content=INTEREST)]}, config)
        assert first["lead_active"] and not leads_db.exists()
        assert "name" in first["messages"][-1].content
        second = graph.invoke({"messages": [HumanMessage(content=DETAILS)]}, config)
        assert "contact number" in second["messages"][-1].content
        assert "occupation" not in second["messages"][-1].content
        assert not leads_db.exists()
    with SqliteSaver.from_conn_string(str(session_db)) as saver:
        graph = build_graph(IndexedStore(), Model(), catalog=load_catalog(), checkpointer=saver, lead_tool=tool)
        final = graph.invoke({"messages": [HumanMessage(content=PHONE)]}, config)
        assert final["lead_saved"] and not final["lead_active"]
        assert not final["error"]
    with sqlite3.connect(leads_db) as conn:
        record = conn.execute("SELECT name,occupation,income,contact_number,product_id,structured_json FROM leads").fetchone()
    assert record[:5] == ("Demo Customer", "freelance", "30000 THB per month", "0812345678", "cheeva")
    assert '"evidence"' in record[5] and '"session_id":"demo"' in record[5]


def test_save_tool_is_idempotent_and_parameterized(tmp_path):
    tool = create_lead_tool(tmp_path / "leads.sqlite")
    record = LeadRecord(lead_id="id", session_id="demo", product_id="cheeva", name="O'Neil; DROP TABLE leads;", occupation="freelance", income="30000 monthly", contact_number="0812345678", evidence={})
    assert tool.invoke({"lead": record.model_dump()})["saved"]
    assert tool.invoke({"lead": record.model_dump()})["saved"]
    with sqlite3.connect(tmp_path / "leads.sqlite") as conn:
        assert conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 1
        assert conn.execute("SELECT name FROM leads").fetchone()[0] == record.name


def test_read_leads_is_session_scoped_and_does_not_create_database(tmp_path):
    from insurex.leads import read_leads
    path = tmp_path / "leads.sqlite"
    assert read_leads(path, "a") == [] and not path.exists()
    tool = create_lead_tool(path)
    for session in ("a", "b"):
        tool.invoke({"lead": LeadRecord(lead_id="id", session_id=session, product_id="cheeva", name="Demo", occupation="freelance", income="30000 monthly", contact_number="0800000000", evidence={}).model_dump()})
    records = read_leads(path, "a")
    assert len(records) == 1 and records[0]["session_id"] == "a"


@pytest.mark.parametrize("phone", ["123", "call me", "08123456781234567", "0812345678@example.com"])
def test_invalid_contact_rejected(phone):
    with pytest.raises(ValueError):
        LeadRecord(lead_id="id", session_id="demo", product_id="cheeva", name="Demo", occupation="freelance", income="30000", contact_number=phone, evidence={})


def test_unsupported_fields_and_premium_budget_cannot_become_income():
    turn = fields("0812345678")
    turn.income = QuotedValue(value="20000", quote="My premium budget is 20000")
    draft = merge_lead(turn, {}, [HumanMessage(content=INTEREST), HumanMessage(content="My premium budget is 20000")], load_catalog())
    assert draft["product_id"] == "cheeva"
    assert all(f not in draft for f in ("name", "occupation", "income", "contact_number"))


def test_cancel_does_not_save_incomplete_details(tmp_path):
    from langgraph.checkpoint.memory import InMemorySaver
    db = tmp_path / "leads.sqlite"
    graph = build_graph(IndexedStore(), Model(), catalog=load_catalog(), checkpointer=InMemorySaver(), lead_tool=create_lead_tool(db))
    config = {"configurable": {"thread_id": "demo"}}
    graph.invoke({"messages": [HumanMessage(content=INTEREST)]}, config)
    result = graph.invoke({"messages": [HumanMessage(content="/cancel-lead")]}, config)
    assert not result["lead_active"] and not result["lead_draft"]
    assert not db.exists()


def test_factual_question_interrupts_collection_without_saving_or_erasing_draft(tmp_path):
    from langgraph.checkpoint.memory import InMemorySaver
    db = tmp_path / "leads.sqlite"
    graph = build_graph(IndexedStore(), Model(), catalog=load_catalog(), checkpointer=InMemorySaver(), lead_tool=create_lead_tool(db))
    config = {"configurable": {"thread_id": "demo"}}
    graph.invoke({"messages": [HumanMessage(content=INTEREST)]}, config)
    result = graph.invoke({"messages": [HumanMessage(content="What is the coverage duration?")]}, config)
    assert "age 90" in result["messages"][-1].content
    assert result["lead_active"] and not db.exists()
    assert result["lead_draft"]["product_id"] == "cheeva"


def test_semantic_interest_trigger_and_no_lead_for_ordinary_question(tmp_path):
    tool = create_lead_tool(tmp_path / "leads.sqlite")
    graph = build_graph(IndexedStore(), Model(), catalog=load_catalog(), lead_tool=tool)
    ordinary = graph.invoke({"messages": [HumanMessage(content="What is Khum Cheeva coverage?")]})
    assert not ordinary.get("lead_active")
    interested = graph.invoke({"messages": [HumanMessage(content="Khum Cheeva sounds like the one I want")]})
    assert interested["lead_active"] and not interested["error"]


def test_invalid_phone_does_not_save_or_erase_other_fields(tmp_path):
    from langgraph.checkpoint.memory import InMemorySaver
    db = tmp_path / "leads.sqlite"
    graph = build_graph(IndexedStore(), Model(), catalog=load_catalog(), checkpointer=InMemorySaver(), lead_tool=create_lead_tool(db))
    config = {"configurable": {"thread_id": "demo"}}
    graph.invoke({"messages": [HumanMessage(content=INTEREST)]}, config)
    graph.invoke({"messages": [HumanMessage(content=DETAILS)]}, config)
    result = graph.invoke({"messages": [HumanMessage(content="My phone is 123.")]}, config)
    assert not db.exists() and result["lead_active"]
    assert result["lead_draft"]["name"]["value"] == "Demo Customer"
    assert "contact_number" not in result["lead_draft"]
    assert "resend" in result["messages"][-1].content
