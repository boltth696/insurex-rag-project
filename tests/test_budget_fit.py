import pytest
from langchain_core.messages import AIMessage, HumanMessage
from insurex.graph import build_graph, FollowupDecision, payment_period_price_intent
from insurex.recommendations import CustomerNeeds, budget_fit_intent
from insurex.catalog import load_catalog

QUESTION = "I don’t have any existing insurance. I want my family to receive ฿1 million if I die. Can you confirm whether either option fits my ฿20,000 annual budget?"


@pytest.mark.parametrize("question", [QUESTION, "Can either plan fit within my annual budget of 20000?", "Is this affordable within my budget?", "แผนนี้อยู่ในงบ 20000 ต่อปีไหม"])
def test_budget_fit_is_distinct_from_payment_duration(question):
    assert budget_fit_intent(question)
    assert not payment_period_price_intent(question)


@pytest.mark.parametrize("question", ["Would paying premiums over five years be cheaper per year than twenty years?", "Do five-year premium payments cost more than twenty-year payments?"])
def test_real_payment_comparison_still_identified(question):
    assert payment_period_price_intent(question)


def test_exact_followup_cannot_be_hijacked_by_earlier_payment_examples():
    class Model:
        def with_structured_output(self, schema):
            assert schema is not FollowupDecision, "Explicit budget fit must bypass the fallible router"
            self.schema = schema
            return self
        def invoke(self, messages):
            assert self.schema is CustomerNeeds
            return CustomerNeeds(goals=["life"], age_quote="age 22", budget_quote="฿20,000 annual budget", goal_quote="I want my family to receive ฿1 million if I die", benefit_quote="฿1 million if I die", existing_coverage_quote="I don’t have any existing insurance")
    state = build_graph(None, Model(), catalog=load_catalog()).invoke({"messages": [
        HumanMessage(content="I want insurance but don’t know where to start."),
        AIMessage(content="Please tell me your age, budget and goal."),
        HumanMessage(content="age 22 annual premium budget 20000 main goal is life protection"),
        AIMessage(content="Compare Cheeva and CI Plus. CI Plus offers five, ten or twenty-year payments."),
        HumanMessage(content=QUESTION),
    ]})
    text = state["messages"][-1].content
    assert state["mode"] == "budget_fit" and not state["error"]
    assert "age 22" in text and "฿20,000 annual budget" in text
    assert "฿1 million if I die" in text and "I don’t have any existing insurance" in text
    assert "cannot confirm" in text and "matching quotes" in text
    assert "35-year-old" not in text and "25,400" not in text
    assert state["sources"] == []


def test_unsupported_requested_amount_is_not_repeated_as_customer_fact():
    from insurex.recommendations import render_budget_fit
    needs = CustomerNeeds(benefit_quote="five million baht on death")
    text = render_budget_fit(needs, [HumanMessage(content="Can this fit my budget?")], "English")
    assert "five million" not in text
    assert "cannot confirm" in text
