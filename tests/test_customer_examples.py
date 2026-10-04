"""Golden customer intent/output tests; live suite separately verifies model interpretation."""
import json
import pytest
from langchain_core.messages import HumanMessage
from insurex.config import ROOT
from insurex.catalog import load_catalog, catalog_intent
from insurex.graph import build_graph, FollowupDecision, GroundedAnswer
from insurex.recommendations import CustomerNeeds
from tests.test_benefits import IndexedStore

CASES = json.loads((ROOT / "demo/customer_examples.json").read_text(encoding="utf-8"))
DETAILS = {"missed_payment": "missed_payment", "hospital_room": "medical_scope", "cancer": "cancer_payment", "diabetes": "eligibility", "waiting": "waiting", "exclusions": "exclusions", "payment_end": "coverage_duration", "cancellation": "cancellation"}


def profile(case):
    key = case["id"]
    if key == "monthly_budget":
        return CustomerNeeds(budget_quote="1,500 a month", missing_details=["age", "existing_coverage"])
    if key == "family":
        return CustomerNeeds(goal_quote="I want them to have money if something happens to me", goal_is_specific=False, question_focus="family_protection", focus_quote="I have two children", missing_details=["age", "budget"])
    if key == "employer_cover":
        return CustomerNeeds(goal_quote="hospital bills", goal_is_specific=False, question_focus="existing_coverage", focus_quote="Do I need more insurance", existing_coverage_quote="My company already pays for hospital bills", missing_details=["age", "budget", "existing_coverage"])
    if key in ("changed_goal", "changed_budget"):
        return CustomerNeeds(goals=["medical"], goal_quote="medical coverage" if key == "changed_goal" else "hospital bills", age_quote="22", budget_quote="50000 baht a year" if key == "changed_goal" else "20,000 a year", missing_details=["existing_coverage"])
    if key == "casual":
        return CustomerNeeds(goals=["medical"], goal_quote="hosp cover", age_quote="22", budget_quote="cheap", missing_details=["existing_coverage"])
    if key == "thai":
        return CustomerNeeds(goals=["medical"], goal_quote="ประกันสุขภาพ", age_quote="22", budget_quote="งบเดือนละ 1,500", missing_details=["existing_coverage"])
    return CustomerNeeds(missing_details=["age", "budget", "existing_coverage"])


class CustomerModel:
    def __init__(self, case, schema=None):
        self.case, self.schema = case, schema
    def with_structured_output(self, schema):
        return CustomerModel(self.case, schema)
    def invoke(self, messages):
        if self.schema is FollowupDecision:
            key = self.case["id"]
            return FollowupDecision(kind="detail" if key in DETAILS else "recommendation", query=self.case["question"], topic=DETAILS.get(key, "general"))
        if self.schema is CustomerNeeds:
            return profile(self.case)
        raise AssertionError("Unscoped examples should not invent product claims")


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_all_customer_examples_get_useful_answers_without_catalog_dump(case):
    graph = build_graph(IndexedStore(), CustomerModel(case), catalog=load_catalog())
    state = graph.invoke({"messages": [HumanMessage(content=q) for q in [*case["setup"], case["question"]]], "profile_context": bool(case["setup"])})
    text = state["messages"][-1].content
    assert state["error"] == ""
    assert state["mode"] != "catalog_list"
    assert "The supplied brochures describe" not in text
    assert "By 'lower mass'" not in text
    key = case["id"]
    if key in DETAILS:
        assert state["answer_topic"] == DETAILS[key]
        assert state["sources"] == []
        assert len(text) > 80
    if key == "monthly_budget":
        assert "age" in text and "main goal" in text
        assert "monthly or annual premium budget" not in text
    if key == "employer_cover":
        assert "Extra insurance is not automatically necessary" in text
        assert "existing insurance coverage." not in text
    if key == "family":
        assert "children" in text and "death benefit" in text
        assert "disabled or ill" in text
        assert "age, premium budget" in text
    if key in ("changed_goal", "changed_budget", "casual"):
        assert "Maojai" in text
        assert "affordability is not yet verified" in text
    if key == "casual":
        assert "monthly or annual premium budget" in text
    if key == "thai":
        assert "คุ้มรักษา" in text
        assert "ยังไม่ใช่การยืนยันว่าอยู่ในงบ" in text


def test_amount_and_payment_frequency_are_not_plain_catalog_options():
    assert catalog_intent("i can only pay 1500 per month what are my options", load_catalog()) is None


def test_ambiguous_family_event_overrides_overconfident_life_classification():
    from insurex.recommendations import render_recommendation
    humans = [HumanMessage(content="I want my children to have money if something happens to me")]
    needs = CustomerNeeds(goals=["life"], goal_quote=humans[0].content, goal_is_specific=True)
    text = render_recommendation(needs, load_catalog(), humans, [], "English")
    assert "death benefit" in text and "disabled or ill" in text
    assert "Candidates to compare" not in text


def test_unknown_details_are_requested_even_if_model_omits_missing_fields():
    from insurex.recommendations import reconcile_known_details
    humans = [HumanMessage(content="I need hospital cover cheap please")]
    needs = reconcile_known_details(CustomerNeeds(budget_quote="cheap", missing_details=[]), humans)
    assert needs.budget_quote == ""
    assert set(needs.missing_details) == {"age", "budget", "existing_coverage"}


def test_generic_insurance_request_quote_is_not_a_protection_goal():
    from insurex.recommendations import render_recommendation
    humans = [HumanMessage(content="I want insurance but don't know where to start")]
    needs = CustomerNeeds(goal_quote=humans[0].content, goal_is_specific=False)
    text = render_recommendation(needs, load_catalog(), humans, [], "English")
    assert "age" in text and "premium budget" in text
    assert "savings or retirement" in text


def test_named_policy_question_still_uses_evidence_instead_of_generic_guard():
    class Model:
        def with_structured_output(self, schema):
            return self
        def invoke(self, messages):
            return GroundedAnswer(supported=True, answer="CI Plus specifies a 90-day waiting period, subject to its stated conditions.", citation_ids=[3])
    state = build_graph(IndexedStore(), Model(), catalog=load_catalog()).invoke({"messages": [HumanMessage(content="What is the waiting period for Khum Talodcheep CI Plus?")]})
    assert "90-day" in state["messages"][-1].content
    assert "Sources:" in state["messages"][-1].content
