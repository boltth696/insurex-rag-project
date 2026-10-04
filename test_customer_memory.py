import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from insurex.catalog import load_catalog
from insurex.graph import build_graph, FollowupDecision
from insurex.recommendations import CustomerNeeds, merge_customer_profile, render_recommendation
from tests.test_benefits import IndexedStore

AGE = "Age 22, annual premium budget ฿20,000, main goal is life protection."
DETAILS = "I don’t have any existing insurance. I want my family to receive ฿1 million if I die."
FAMILY = "I have two children. I want them to have money if something happens to me"


def full_profile():
    return CustomerNeeds(age_quote="Age 22", budget_quote="annual premium budget ฿20,000", goals=["life"], goal_quote="I want my family to receive ฿1 million if I die", benefit_quote="฿1 million if I die", existing_coverage_quote="I don’t have any existing insurance", coverage_status="none")


def test_same_session_family_followup_remembers_profile_even_when_model_omits_it():
    class Model:
        def __init__(self, schema=None):
            self.schema = schema
        def with_structured_output(self, schema):
            return Model(schema)
        def invoke(self, messages):
            latest = next(m.content for m in reversed(messages) if isinstance(m, HumanMessage))
            if self.schema is FollowupDecision:
                return FollowupDecision(kind="recommendation", query=latest)
            if latest == FAMILY:
                return CustomerNeeds(question_focus="family_protection", focus_quote="I have two children", goal_quote="if something happens to me", goal_is_specific=False, missing_details=["age", "budget", "existing_coverage"])
            return full_profile()
    graph = build_graph(IndexedStore(), Model(), catalog=load_catalog(), checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "same-customer"}}
    first = graph.invoke({"messages": [HumanMessage(content=AGE), HumanMessage(content=DETAILS)]}, config)
    assert first["customer_profile"]["coverage_status"] == "none"
    assert "You said you have no existing insurance" in first["messages"][-1].content
    last = graph.invoke({"messages": [HumanMessage(content=FAMILY)]}, config)
    text = last["messages"][-1].content
    assert "previously stated a death-benefit goal" in text
    assert "disabled or ill" in text
    assert "Age 22" in text and "฿20,000" in text and "฿1 million" in text
    assert "Please provide your" not in text
    assert last["customer_profile"]["coverage_status"] == "none"


@pytest.mark.parametrize("statement", ["I don’t have any existing insurance", "I do not have any insurance", "I have no existing insurance", "ไม่มีประกัน"])
def test_negative_coverage_never_becomes_existing_benefits(statement):
    humans = [HumanMessage(content=AGE), HumanMessage(content=statement)]
    needs = CustomerNeeds(goals=["life"], goal_quote="life protection", existing_coverage_quote=statement, coverage_status="current")
    from insurex.recommendations import reconcile_known_details
    needs = reconcile_known_details(needs, humans)
    assert needs.coverage_status == "none"
    assert "existing_coverage" not in needs.missing_details
    docs = IndexedStore()
    sources = [{"id": i, "file": d.metadata["source"], "page": d.metadata["page"]} for i, d in enumerate(docs.docs.values(), 1)]
    text = render_recommendation(needs, load_catalog(), humans, sources, "English")
    assert "You said you have no existing insurance" in text
    assert "check its benefits" not in text


def test_later_budget_and_coverage_correction_override_saved_profile():
    updated = "My budget is now 30000 a year. My company now covers hospital bills."
    humans = [HumanMessage(content=AGE), HumanMessage(content=DETAILS), HumanMessage(content=updated)]
    needs = merge_customer_profile(CustomerNeeds(budget_quote="30000 a year", existing_coverage_quote="My company now covers hospital bills", coverage_status="current"), full_profile().model_dump(), humans)
    assert needs.budget_quote == "30000 a year"
    assert needs.coverage_status == "current"
    assert needs.age_quote == "Age 22"


def test_new_customer_does_not_inherit_old_profile_even_if_extractor_is_stale():
    latest = "This is a different customer. She wants medical insurance."
    humans = [HumanMessage(content=AGE), HumanMessage(content=DETAILS), HumanMessage(content=latest)]
    needs = full_profile().model_copy(update={"new_customer_quote": "This is a different customer"})
    result = merge_customer_profile(needs, full_profile().model_dump(), humans)
    assert result.age_quote == "" and result.budget_quote == ""
    assert result.benefit_quote == "" and result.existing_coverage_quote == ""
    assert result.coverage_status == "unknown" and result.goals == []
    assert set(result.missing_details) == {"age", "budget", "existing_coverage"}


def test_profile_is_isolated_between_sessions():
    class Model:
        def with_structured_output(self, schema):
            self.schema = schema
            return self
        def invoke(self, messages):
            if self.schema is FollowupDecision:
                return FollowupDecision(kind="recommendation", query=FAMILY)
            if any(isinstance(m, HumanMessage) and m.content == DETAILS for m in messages):
                return full_profile()
            return CustomerNeeds(question_focus="family_protection", focus_quote="I have two children", goal_quote="if something happens to me", goal_is_specific=False)
    graph = build_graph(IndexedStore(), Model(), catalog=load_catalog(), checkpointer=InMemorySaver())
    graph.invoke({"messages": [HumanMessage(content=AGE), HumanMessage(content=DETAILS)]}, {"configurable": {"thread_id": "a"}})
    result = graph.invoke({"messages": [HumanMessage(content=FAMILY)]}, {"configurable": {"thread_id": "b"}})
    assert "Please provide your age, premium budget" in result["messages"][-1].content
    assert "฿20,000" not in result["messages"][-1].content


def test_customer_profile_survives_sqlite_restart(tmp_path):
    from langgraph.checkpoint.sqlite import SqliteSaver
    class Model:
        def __init__(self, schema=None):
            self.schema = schema
        def with_structured_output(self, schema):
            return Model(schema)
        def invoke(self, messages):
            latest = next(m.content for m in reversed(messages) if isinstance(m, HumanMessage))
            if self.schema is FollowupDecision:
                return FollowupDecision(kind="recommendation", query=latest)
            return (CustomerNeeds(question_focus="family_protection", focus_quote="I have two children", goal_quote="something happens to me", goal_is_specific=False) if latest == FAMILY else full_profile())
    db = str(tmp_path / "session.sqlite")
    config = {"configurable": {"thread_id": "same-customer"}}
    with SqliteSaver.from_conn_string(db) as saver:
        graph = build_graph(IndexedStore(), Model(), catalog=load_catalog(), checkpointer=saver)
        graph.invoke({"messages": [HumanMessage(content=AGE), HumanMessage(content=DETAILS)]}, config)
    with SqliteSaver.from_conn_string(db) as saver:
        graph = build_graph(IndexedStore(), Model(), catalog=load_catalog(), checkpointer=saver)
        result = graph.invoke({"messages": [HumanMessage(content=FAMILY)]}, config)
    text = result["messages"][-1].content
    assert "Age 22" in text and "฿20,000" in text and "฿1 million" in text
    assert "Please provide your" not in text
