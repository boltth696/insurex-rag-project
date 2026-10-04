import pytest
from langchain_core.messages import HumanMessage, AIMessage
from insurex.catalog import catalog_intent, load_catalog
from insurex.comparison import comparison_intent
from insurex.graph import build_graph, GroundedAnswer, FollowupDecision
from tests.test_benefits import IndexedStore
from insurex.recommendations import CustomerNeeds, render_recommendation, reconcile_known_details, render_profile


@pytest.mark.parametrize("question", [
    "which product would you recommend best for lower mass group of customer",
    "Which products are best for customers with a low budget?",
    "What plans would you suggest for young families?",
    "Which policy is suitable for me?",
    "Which policy is better for retirement?",
    "มีประกันอะไรเหมาะกับคนรายได้น้อยบ้าง",
    "แนะนำประกันสำหรับลูกค้างบน้อย",
    "Which plan suits a poor customer with money set aside for treatment?",
])
def test_suitability_questions_never_route_to_catalog(question):
    assert comparison_intent(question) == "recommendation"
    assert catalog_intent(question, load_catalog()) is None


def test_exact_customer_question_uses_all_brochures_and_clarification_prompt():
    class Model:
        def with_structured_output(self, schema):
            return self
        def invoke(self, messages):
            self.messages = messages
            return CustomerNeeds(ambiguous_segment=True)
    model = Model()
    state = build_graph(IndexedStore(), model, catalog=load_catalog(), top_k=1).invoke({"messages": [
        HumanMessage(content="what products are there to choose from"),
        AIMessage(content="A previous catalog reply"),
        HumanMessage(content="which product would you recommend best for lower mass group of customer"),
    ]})
    assert state["mode"] == "recommendation"
    assert len(state["sources"]) == 16
    assert len({s["file"] for s in state["sources"]}) == 5
    instructions = "\n".join(str(m.content) for m in model.messages[:3])
    assert "Shorter payment periods do not establish affordability" in instructions
    assert "Interpret meaning" in instructions
    assert "To suggest suitable products" in state["messages"][-1].content
    assert "The supplied brochures describe" not in state["messages"][-1].content


def test_plain_catalog_question_remains_fast():
    state = build_graph(None, None, catalog=load_catalog()).invoke({"messages": [HumanMessage(content="What products are there to choose from?")]})
    assert state["mode"] == "catalog_list"


def test_actual_budget_followup_clarifies_generic_protection_and_keeps_route():
    class Model:
        def with_structured_output(self, schema):
            assert schema in (GroundedAnswer, CustomerNeeds, FollowupDecision)
            return self
        def invoke(self, messages):
            assert all(not isinstance(m, AIMessage) for m in messages)
            # Reproduce the actual model failure: stale segment and missing fields.
            return CustomerNeeds(goals=[], ambiguous_segment=True, missing_details=["age", "budget", "existing_coverage"])
    graph = build_graph(IndexedStore(), Model(), catalog=load_catalog())
    state = graph.invoke({"mode": "recommendation", "messages": [
        HumanMessage(content="which product would you recommend best for lower mass group of customer"),
        AIMessage(content="Cheeva is affordable and CI Plus has higher premiums"),
        HumanMessage(content="budget concious customer 22 years old buget arounnd 50000 yearly main goal is protection"),
    ]})
    text = state["messages"][-1].content
    assert state["mode"] == "recommendation"
    assert "What kind of protection" in text
    assert "Budget fit remains unverified" in text
    assert "Cheeva" not in text
    assert state["error"] == ""


@pytest.mark.parametrize("wording", ["frugal", "careful with money", "cost-sensitive", "has limited means"])
def test_concrete_profile_does_not_need_a_segment_keyword(wording):
    text = "{} customer 22 years old buget arounnd 50000 yearly main goal is protection".format(wording)
    needs = reconcile_known_details(CustomerNeeds(ambiguous_segment=True), [HumanMessage(content="lower mass"), HumanMessage(content=text)])
    assert not needs.ambiguous_segment


def test_semantic_segment_and_profile_quotes_accept_unfamiliar_paraphrases():
    humans = [HumanMessage(content="lower mass"), HumanMessage(content="Keeps a tight rein on spending; just turned twenty two; can set aside fifty thousand baht each year; wants help with treatment costs")]
    needs = reconcile_known_details(CustomerNeeds(ambiguous_segment=True, segment="cost_sensitive", segment_quote="Keeps a tight rein on spending", age_quote="just turned twenty two", budget_quote="fifty thousand baht each year", missing_details=["age", "budget"]), humans)
    assert not needs.ambiguous_segment
    assert needs.missing_details == ["existing_coverage"]


def test_fabricated_semantic_segment_cannot_clear_ambiguity():
    needs = reconcile_known_details(CustomerNeeds(ambiguous_segment=True, segment="cost_sensitive", segment_quote="frugal", age_quote="age 22", budget_quote="50000 yearly", missing_details=["age", "budget"]), [HumanMessage(content="lower mass")])
    assert needs.ambiguous_segment
    assert needs.missing_details == ["age", "budget", "existing_coverage"]


@pytest.mark.parametrize("history", [[], [HumanMessage(content="lower mass customers")]])
def test_generic_recommendation_never_mentions_old_or_invented_lower_mass(history):
    text = render_recommendation(CustomerNeeds(ambiguous_segment=True), load_catalog(), [*history, HumanMessage(content="what product could you recommend me")], [], "English")
    assert "lower mass" not in text
    assert "age" in text and "premium budget" in text and "main goal" in text


def test_generic_request_with_existing_profile_keeps_valid_candidates():
    quote = "help paying hospital bills"
    store = IndexedStore()
    sources = [{"id": i, "file": d.metadata["source"], "page": d.metadata["page"]} for i, d in enumerate(store.docs.values(), 1)]
    text = render_recommendation(CustomerNeeds(ambiguous_segment=True, goals=["medical"], goal_quote=quote), load_catalog(), [HumanMessage(content="lower mass"), HumanMessage(content=quote), HumanMessage(content="what product could you recommend me")], sources, "English")
    assert "Maojai" in text
    assert "lower mass" not in text


@pytest.mark.parametrize("segment", ["lower mass", "medium mass", "high mass", "affluent", "wealthy", "poor", "frugal", "middle income", "some other segment"])
def test_any_segment_without_details_asks_for_profile_not_an_assumed_income(segment):
    text = render_recommendation(CustomerNeeds(ambiguous_segment=True), load_catalog(), [HumanMessage(content=f"What product would you recommend for {segment} customers?")], [], "English")
    assert "To suggest suitable products" in text
    assert "premium budget" in text and "main goal" in text
    assert "By 'lower mass'" not in text
    assert "Candidates" not in text


@pytest.mark.parametrize("segment", ["medium mass", "high mass", "affluent", "poor"])
def test_any_segment_with_explicit_medical_goal_uses_actual_goal(segment):
    quote = "help paying treatment costs"
    store = IndexedStore()
    sources = [{"id": i, "file": d.metadata["source"], "page": d.metadata["page"]} for i, d in enumerate(store.docs.values(), 1)]
    text = render_recommendation(CustomerNeeds(ambiguous_segment=True, goals=["medical"], goal_quote=quote), load_catalog(), [HumanMessage(content=f"{segment} customer wants {quote}")], sources, "English")
    assert "Maojai" in text
    assert "lower mass" not in text


def test_semantic_medical_goal_does_not_require_medical_keyword():
    quote = "help with treatment costs"
    store = IndexedStore()
    sources = [{"id": i, "file": d.metadata["source"], "page": d.metadata["page"]} for i, d in enumerate(store.docs.values(), 1)]
    text = render_recommendation(CustomerNeeds(goals=["medical"], goal_quote=quote, goal_is_specific=True), load_catalog(), [HumanMessage(content=quote)], sources, "English")
    assert "Maojai" in text


@pytest.mark.parametrize("segment", ["budget concious", "frugal", "careful with money"])
def test_actual_repeated_exchange_recovers_even_when_extractor_keeps_stale_flag(segment):
    from langgraph.checkpoint.memory import InMemorySaver
    class StaleModel:
        def with_structured_output(self, schema):
            return self
        def invoke(self, messages):
            return CustomerNeeds(ambiguous_segment=True, missing_details=["age", "budget"])
    graph = build_graph(IndexedStore(), StaleModel(), catalog=load_catalog(), checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "repeat-exact-incident"}}
    first = graph.invoke({"messages": [HumanMessage(content="which product would you recommend best for lower mass group of customer")]}, config)
    assert "To suggest suitable products" in first["messages"][-1].content
    reply = segment + " customer 22 years old buget arounnd 50000 yearly main goal is protection"
    for _ in range(2):
        state = graph.invoke({"messages": [HumanMessage(content=reply)]}, config)
        assert "What kind of protection" in state["messages"][-1].content
        assert "By 'lower mass'" not in state["messages"][-1].content
        assert state["error"] == ""


@pytest.mark.parametrize("clarification", ["budget concious customer", "budget-conscious customers", "lower income customers", "ลูกค้ารายได้น้อย"])
def test_explicit_segment_clarification_overrides_model(clarification):
    needs = reconcile_known_details(CustomerNeeds(ambiguous_segment=True, missing_details=["age", "budget"]), [HumanMessage(content="lower mass"), HumanMessage(content=clarification + " 22 years old buget arounnd 50000 yearly")])
    assert not needs.ambiguous_segment
    assert needs.missing_details == ["existing_coverage"]


def test_new_ambiguous_segment_is_not_overridden_by_old_profile():
    needs = reconcile_known_details(CustomerNeeds(ambiguous_segment=True), [HumanMessage(content="budget conscious"), HumanMessage(content="Now consider a different lower mass group")])
    assert needs.ambiguous_segment


@pytest.mark.parametrize("goal,quote,expected", [
    ("life", "money for my family when I die", ["Cheeva", "CI Plus"]),
    ("critical_illness", "a lump sum for critical illness", ["CI Plus", "Cheeva"]),
    ("medical", "help paying medical bills", ["Maojai"]),
    ("savings", "savings", ["Aomsook"]),
    ("retirement", "retirement", ["Bamnan"]),
])
def test_controlled_shortlist_never_invents_budget_fit_or_price_ranking(goal, quote, expected):
    catalog = load_catalog()
    docs = IndexedStore().docs.values()
    sources = [{"id": i, "file": d.metadata["source"], "page": d.metadata["page"]} for i, d in enumerate(docs, 1)]
    text = render_recommendation(CustomerNeeds(goals=[goal], goal_quote=quote), catalog, [HumanMessage(content=quote)], sources, "English")
    for name in expected:
        assert name in text
    assert "No comparable quotes" in text
    assert "cannot confirm" in text
    assert "higher premiums" not in text
    assert "designed to be affordable" not in text
    assert "Sources:" in text
    if goal == "medical":
        assert "base life policy" in text
    if goal in ("life", "critical_illness"):
        assert "not automatically included" in text


def test_invented_customer_goal_quote_is_rejected():
    with pytest.raises(ValueError, match="human-message quote"):
        render_recommendation(CustomerNeeds(goals=["life"], goal_quote="death benefits"), load_catalog(), [HumanMessage(content="protection")], [], "English")


def test_thai_generic_protection_clarification():
    text = render_recommendation(CustomerNeeds(), load_catalog(), [], [], "Thai")
    assert "ค่ารักษาพยาบาล" in text
    assert "ใบเสนอราคา" in text


def test_model_cannot_convert_generic_protection_quote_to_life_preference():
    text = render_recommendation(CustomerNeeds(goals=["life"], goal_quote="main goal is protection"), load_catalog(), [HumanMessage(content="main goal is protection")], [], "English")
    assert "What kind of protection" in text
    assert "Cheeva" not in text


@pytest.mark.parametrize("question", [
    "What age, annual budget, and current protection goal have I told you?",
    "Summarize my customer profile",
    "What have I already mentioned about my budget?",
    "สรุปข้อมูลของฉัน",
])
def test_profile_recall_answers_history_without_search_or_shortlist(question):
    class Model:
        def with_structured_output(self, schema):
            return self
        def invoke(self, messages):
            assert all(not isinstance(m, AIMessage) for m in messages)
            return CustomerNeeds(age_quote="22", budget_quote="฿50,000 per year", goal_quote="a lump sum if I get seriously ill", goals=["critical_illness"])
    state = build_graph(None, Model(), catalog=load_catalog()).invoke({"mode": "recommendation", "messages": [
        HumanMessage(content="I mainly want help paying hospital bills. I’m 22 and can spend around ฿50,000 per year"),
        AIMessage(content="You are 40 and have a budget of 100,000"),
        HumanMessage(content="Actually, I want a lump sum if I get seriously ill, rather than reimbursement of hospital bills. Keep my age and budget the same"),
        HumanMessage(content=question),
    ]})
    text = state["messages"][-1].content
    assert state["mode"] == "profile_recall"
    assert "22" in text and "฿50,000 per year" in text
    assert "a lump sum if I get seriously ill" in text
    assert "Candidates" not in text
    assert "40" not in text
    assert state["sources"] == []
    assert state["error"] == ""


def test_profile_recall_does_not_echo_invented_values():
    text = render_profile(CustomerNeeds(age_quote="age 40", budget_quote="100000 yearly"), [HumanMessage(content="I am 22")], "English")
    assert "40" not in text and "100000" not in text
    assert "Not verified" in text


@pytest.mark.parametrize("latest", [
    "Frugal customer, 22 years old, budget around ฿50,000 yearly. The main goal is protection",
    "My priority is protection.",
    "เป้าหมายหลักคือความคุ้มครอง",
])
def test_new_broad_goal_overrides_old_specific_goal(latest):
    old = "I want a lump sum if I get seriously ill"
    needs = CustomerNeeds(goals=["critical_illness"], goal_quote=old)
    humans = [HumanMessage(content=old), HumanMessage(content=latest)]
    result = reconcile_known_details(needs, humans)
    assert result.goals == []
    assert not result.goal_is_specific
    assert result.goal_quote in latest
    text = render_recommendation(needs, load_catalog(), humans, [], "English")
    assert "What kind of protection" in text
    assert "Candidates" not in text
    recalled = render_profile(needs, humans, "English")
    assert old not in recalled


def test_later_specific_goal_resolves_broad_goal_again():
    humans = [HumanMessage(content="The main goal is protection"), HumanMessage(content="I want help paying hospital bills")]
    needs = CustomerNeeds(goals=["medical"], goal_quote="help paying hospital bills")
    result = reconcile_known_details(needs, humans)
    assert result.goals == ["medical"]


def test_memory_question_does_not_reset_old_goal():
    quote = "a lump sum if I get seriously ill"
    humans = [HumanMessage(content=quote), HumanMessage(content="What age, annual budget, and current protection goal have I told you?")]
    result = reconcile_known_details(CustomerNeeds(goals=["critical_illness"], goal_quote=quote), humans)
    assert result.goals == ["critical_illness"]


def test_actual_restart_session_with_stale_goal_returns_clarification():
    class StaleGoalModel:
        def with_structured_output(self, schema):
            return self
        def invoke(self, messages):
            return CustomerNeeds(goals=["critical_illness"], goal_quote="a lump sum if I get seriously ill")
    state = build_graph(IndexedStore(), StaleGoalModel(), catalog=load_catalog()).invoke({"mode": "recommendation", "messages": [
        HumanMessage(content="I want a lump sum if I get seriously ill"),
        AIMessage(content="Compare CI Plus and Cheeva"),
        HumanMessage(content="Frugal customer, 22 years old, budget around ฿50,000 yearly. The main goal is protection"),
    ]})
    assert "What kind of protection" in state["messages"][-1].content
    assert "Candidates" not in state["messages"][-1].content
    assert state["error"] == ""


def test_total_budget_question_answers_detail_instead_of_restarting_shortlist():
    class Model:
        def __init__(self, schema=None):
            self.schema = schema
        def with_structured_output(self, schema):
            return Model(schema)
        def invoke(self, messages):
            if self.schema is FollowupDecision:
                return FollowupDecision(kind="detail", query="Does the annual total budget for Khum Raksa Maojai Extra need to cover both its base life policy and health rider?")
            return GroundedAnswer(supported=True, answer="Yes. Include both premiums in the total budget; the brochure does not verify a combined quote for you.", citation_ids=[1, 4])
    state = build_graph(IndexedStore(), Model(), catalog=load_catalog()).invoke({"mode": "recommendation", "messages": [
        HumanMessage(content="I mainly want help paying hospital bills"),
        AIMessage(content="Khum Raksa Maojai Extra is a health rider"),
        HumanMessage(content="Does my ฿50,000 annual budget need to cover both the main policy and the health rider?"),
    ]})
    assert state["mode"] == "single"
    text = state["messages"][-1].content
    assert text.startswith("Yes")
    assert "both" in text and "quote" in text
    assert "What kind of protection" not in state["messages"][-1].content


@pytest.mark.parametrize("question", [
    "Which of those products is cheaper for me?",
    "Which plan definitely fits that budget?",
    "Which product has the lowest price?",
    "Which products cover treatment costs?",
])
def test_price_and_suitability_questions_do_not_become_catalog_lists(question):
    assert catalog_intent(question, load_catalog()) is None


def test_profile_changes_after_detail_question_use_semantic_followup_route():
    class Model:
        def __init__(self, schema=None):
            self.schema = schema
        def with_structured_output(self, schema):
            return Model(schema)
        def invoke(self, messages):
            if self.schema is FollowupDecision:
                return FollowupDecision(kind="recommendation", query="Update annual budget to 18000 baht, keep age 22 and hospital-bill goal")
            return CustomerNeeds(goals=["medical"], goal_quote="hospital bills", age_quote="22", budget_quote="18000 baht per year")
    state = build_graph(IndexedStore(), Model(), catalog=load_catalog()).invoke({"mode": "single", "profile_context": True, "messages": [
        HumanMessage(content="I am 22 and want help with hospital bills"),
        AIMessage(content="Total premiums include the base policy and rider"),
        HumanMessage(content="Correction: budget is 18000 baht per year"),
    ]})
    assert state["mode"] == "recommendation"
    assert "Maojai" in state["messages"][-1].content
    assert state["error"] == ""


def test_customer_price_ranking_never_uses_free_model_claims():
    class FailIfAsked:
        def with_structured_output(self, schema):
            return self
        def invoke(self, messages):
            raise AssertionError("Price ranking should use the uncertainty guard")
    state = build_graph(IndexedStore(), FailIfAsked(), catalog=load_catalog()).invoke({"messages": [HumanMessage(content="Is Khum Cheeva cheaper than Khum Talodcheep CI Plus for me?")]})
    assert "I cannot confirm" in state["messages"][-1].content
    assert "more likely" not in state["messages"][-1].content
    assert state["error"] == ""


def test_partial_semantic_hit_expands_to_complete_premium_table():
    class PartialStore(IndexedStore):
        def similarity_search(self, *args, **kwargs):
            chunks = [d for d in self.docs.values() if d.metadata["source"].startswith("11_") and d.metadata["page"] == 2]
            return chunks[-1:]
    class FailIfAsked:
        def with_structured_output(self, schema):
            return self
        def invoke(self, messages):
            raise AssertionError("Reviewed payment-price comparison should bypass free generation")
    state = build_graph(PartialStore(), FailIfAsked(), catalog=load_catalog()).invoke({"messages": [HumanMessage(content="Would paying premiums over five years be cheaper per year than twenty years?")]})
    text = state["messages"][-1].content
    assert "25,400" in text and "7,200" in text
    assert "35-year-old male" in text and "THB 200,000" in text
    assert "cost more per year" in text
    assert not text.startswith("Yes")
    assert "not quotes for your customer" in text
    assert state["error"] == ""
