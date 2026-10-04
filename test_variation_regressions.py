from langchain_core.messages import HumanMessage
from insurex.leads import LeadTurn, QuotedValue, merge_lead, lead_interest_intent
from insurex.catalog import load_catalog
from insurex.graph import build_graph, FollowupDecision
from insurex.recommendations import CustomerNeeds
from langgraph.checkpoint.memory import InMemorySaver
from tests.test_benefits import IndexedStore
import pytest


def test_conditional_interest_is_not_an_actual_request_to_collect():
    assert not lead_interest_intent("If I am interested in Khum Cheeva, what information would you need?")


def test_lead_correction_is_not_replaced_by_an_older_supported_quote():
    humans = [HumanMessage(content="I earn 40000 monthly"), HumanMessage(content="Correction, my income is 30000 monthly")]
    prior = {"income": {"value": "30000 monthly", "quote": "my income is 30000 monthly"}}
    turn = LeadTurn(income=QuotedValue(value="40000 monthly", quote="I earn 40000 monthly"))
    assert merge_lead(turn, prior, humans, load_catalog())["income"]["value"] == "30000 monthly"


def test_new_customer_scope_stays_reset_on_later_followups():
    class Model:
        def __init__(self, schema=None):
            self.schema = schema
        def with_structured_output(self, schema):
            return Model(schema)
        def invoke(self, messages):
            latest = next(m.content for m in reversed(messages) if isinstance(m, HumanMessage))
            if self.schema is FollowupDecision:
                return FollowupDecision(kind="recommendation", query=latest)
            if "different" in latest:
                return CustomerNeeds(new_customer_quote="This is a different customer", age_quote="age 45", goals=["medical"], goal_quote="wants hospital bills paid")
            return CustomerNeeds(age_quote="age 22", budget_quote="50000 yearly", goals=["medical"], goal_quote="wants hospital bills paid" if "She" in latest else "want hospital cover")
    graph = build_graph(IndexedStore(), Model(), catalog=load_catalog(), checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "boundary"}}
    graph.invoke({"messages": [HumanMessage(content="age 22, budget 50000 yearly, want hospital cover")]}, config)
    graph.invoke({"messages": [HumanMessage(content="This is a different customer, age 45, wants hospital bills paid")]}, config)
    result = graph.invoke({"messages": [HumanMessage(content="She has no insurance. What else do you need?")]}, config)
    assert result["customer_profile"]["age_quote"] == "age 45"
    assert result["customer_profile"]["budget_quote"] == ""
    assert "50000" not in result["messages"][-1].content


@pytest.mark.parametrize("a,b,expected,absent", [(5,10,["25,400","13,000"],"7,200"),(10,20,["13,000","7,200"],"25,400"),(20,5,["7,200","25,400"],"13,000")])
def test_reviewed_example_uses_requested_payment_options(a,b,expected,absent):
    from insurex.graph import reviewed_payment_example
    sources = [{"id": 1, "file": "11_example.pdf", "page": 2}]
    text = reviewed_payment_example(f"Compare {a}-year and {b}-year premium payments for CI Plus Plan 1", sources, "English")
    assert all(value in text for value in expected)
    assert absent not in text
    assert "35-year-old" in text and "200,000" in text


def test_plan_two_cannot_inherit_plan_one_price_example():
    from insurex.graph import reviewed_payment_example
    text = reviewed_payment_example("Plan 2 five-year vs twenty-year payments", [{"id":1,"file":"11_example.pdf","page":2}], "English")
    assert "63,500" in text and "18,000" in text and "500,000" in text
    assert "25,400" not in text and "200,000" not in text


@pytest.mark.parametrize("quote,text,expected", [("22","budget 22000",False),("22","age 22 budget 22000",True),("30000","income 130000",False),("22","I am 22 years old",True),("22","age 222",False),("22","age 122",False),("20,000","budget 120,000",False),("20000","budget 20000 annually",True),("22","age ２２",True),("20","budget 20,000",False),("000","budget 20,000",False),("22","age 22.5",False),("50","budget 50.25",False),("22","age 22, budget 20000",True),("20","ages 20,21",True)])
def test_customer_numeric_quote_boundaries(quote,text,expected):
    from insurex.customer_evidence import contains_customer_quote
    assert contains_customer_quote(quote,text) == expected


def test_age_quote_position_ignores_later_budget_containing_age_digits():
    from insurex.customer_evidence import customer_quote_position
    humans = [HumanMessage(content="age 22"),HumanMessage(content="Actually age 33"),HumanMessage(content="Budget 22000 yearly")]
    assert customer_quote_position("22",humans) == 0
    assert customer_quote_position("33",humans) == 1


def test_profile_renderer_does_not_read_age_from_budget_digits():
    from insurex.recommendations import render_profile
    text = render_profile(CustomerNeeds(age_quote="22"), [HumanMessage(content="budget 22000 yearly")], "English")
    assert "Age: Not verified" in text


def test_combined_budget_question_answers_current_question_not_generic_fallback():
    class NoGeneration:
        def with_structured_output(self, schema):
            return self
        def invoke(self, messages):
            raise AssertionError("Combined-cost fact must not depend on generation")
    question = "Does my ฿50,000 annual budget need to cover both the main policy and the health rider?"
    result = build_graph(IndexedStore(), NoGeneration(), catalog=load_catalog()).invoke({"messages":[HumanMessage(content=question)]})
    text = result["messages"][-1].content
    assert result["answer_topic"] == "combined_premium"
    assert "both the main life policy premium and the health rider premium" in text
    assert "Matching quotes" in text and "Sources:" in text
    assert not result["error"]


def test_combined_cheeva_ci_rider_budget_does_not_become_a_health_rider():
    class NoGeneration:
        def with_structured_output(self, schema):
            return self
        def invoke(self, messages):
            raise AssertionError("Combined-cost fact must not depend on generation")
    question = "Does my budget for Khum Cheeva need to cover both the main policy and CI 50 rider?"
    result = build_graph(IndexedStore(), NoGeneration(), catalog=load_catalog()).invoke({"messages":[HumanMessage(content=question)]})
    text = result["messages"][-1].content
    assert "health rider" not in text
    assert "attached rider premium" in text
    assert "02_SCB" in text and "07_SCB" not in text


def test_changed_goal_does_not_carry_death_benefit_into_medical_budget_answer():
    from insurex.recommendations import merge_customer_profile, render_budget_fit
    humans = [HumanMessage(content="I want my family to receive 1 million if I die"), HumanMessage(content="Actually I only want hospital bills paid")]
    previous = CustomerNeeds(goals=["life"], goal_quote=humans[0].content, benefit_quote=humans[0].content)
    extracted = CustomerNeeds(goals=["medical"], goal_quote=humans[1].content, benefit_quote=humans[0].content)
    merged = merge_customer_profile(extracted, previous.model_dump(), humans)
    assert merged.benefit_quote == ""
    assert "1 million" not in render_budget_fit(merged, humans, "English")


def test_adding_another_goal_preserves_original_death_benefit():
    from insurex.recommendations import merge_customer_profile
    humans = [HumanMessage(content="1 million if I die"), HumanMessage(content="I also want help with medical bills")]
    previous = CustomerNeeds(goals=["life"], goal_quote=humans[0].content, benefit_quote=humans[0].content)
    extracted = CustomerNeeds(goals=["life", "medical"], goal_quote=humans[1].content)
    merged = merge_customer_profile(extracted, previous.model_dump(), humans)
    assert merged.benefit_quote == humans[0].content


def test_profile_recall_during_lead_collection_preserves_draft(tmp_path):
    from tests.test_leads import Model as LeadModel, INTEREST
    from insurex.leads import create_lead_tool
    class Model(LeadModel):
        def with_structured_output(self, schema):
            return Model(schema)
        def invoke(self, messages):
            if self.schema is CustomerNeeds:
                return CustomerNeeds(age_quote="age 22", budget_quote="20000 yearly", goals=["life"], goal_quote="life protection")
            return super().invoke(messages)
    graph = build_graph(IndexedStore(), Model(), catalog=load_catalog(), checkpointer=InMemorySaver(), lead_tool=create_lead_tool(tmp_path / "leads.sqlite"))
    config = {"configurable":{"thread_id":"lead-recall"}}
    graph.invoke({"messages":[HumanMessage(content="age 22, budget 20000 yearly, life protection"), HumanMessage(content=INTEREST)]}, config)
    result = graph.invoke({"messages":[HumanMessage(content="What age and budget have I told you?")]}, config)
    assert result["mode"] == "profile_recall"
    assert "22" in result["messages"][-1].content and "20000" in result["messages"][-1].content
    assert result["lead_active"] and result["lead_draft"]["product_id"] == "cheeva"
    assert not (tmp_path / "leads.sqlite").exists()


def test_different_customer_does_not_inherit_unfinished_lead_details(tmp_path):
    from insurex.leads import create_lead_tool
    class Model:
        def __init__(self, schema=None):
            self.schema = schema
        def with_structured_output(self, schema):
            return Model(schema)
        def invoke(self, messages):
            assert self.schema is LeadTurn
            latest = next(m.content for m in reversed(messages) if isinstance(m, HumanMessage))
            if "different" in latest:
                return LeadTurn(product_id="aomsook", product_quote="Khum Aomsook", new_customer_quote="different customer", name=QuotedValue(value="Test Beta", quote="Test Beta"))
            return LeadTurn(product_id="cheeva", product_quote="Khum Cheeva", name=QuotedValue(value="Test Alpha",quote="Test Alpha"), occupation=QuotedValue(value="student",quote="student"), income=QuotedValue(value="20000 monthly",quote="income 20000 monthly"))
    db = tmp_path / "leads.sqlite"
    graph = build_graph(IndexedStore(), Model(), catalog=load_catalog(), checkpointer=InMemorySaver(), lead_tool=create_lead_tool(db))
    config = {"configurable":{"thread_id":"lead-new-customer"}}
    first = graph.invoke({"messages":[HumanMessage(content="I am interested in Khum Cheeva. Test Alpha, student, income 20000 monthly")]}, config)
    second = graph.invoke({"messages":[HumanMessage(content="Now a different customer, Test Beta. I am interested in Khum Aomsook")]}, config)
    assert second["lead_draft"]["name"]["value"] == "Test Beta"
    assert "occupation" not in second["lead_draft"] and "income" not in second["lead_draft"]
    assert second["lead_id"] != first["lead_id"]
    assert not db.exists()


@pytest.mark.parametrize("failure", ["exception", "unconfirmed"])
def test_failed_lead_save_never_claims_success_and_keeps_retry_details(failure):
    class Tool:
        def invoke(self, record):
            if failure == "exception":
                raise OSError("Synthetic local database failure")
            return {"saved":False}
    class Model:
        def with_structured_output(self, schema):
            return self
        def invoke(self, messages):
            return LeadTurn(product_id="cheeva",product_quote="Khum Cheeva",name=QuotedValue(value="Test Alpha",quote="Test Alpha"), occupation=QuotedValue(value="student",quote="student"),income=QuotedValue(value="20000 monthly",quote="income 20000 monthly"),contact_number=QuotedValue(value="0800000000",quote="0800000000"))
    graph = build_graph(IndexedStore(),Model(),catalog=load_catalog(),lead_tool=Tool())
    result = graph.invoke({"lead_saved":True,"messages":[HumanMessage(content="I am interested in Khum Cheeva. Test Alpha, student, income 20000 monthly, 0800000000")]},{"configurable":{"thread_id":"failed-save"}})
    assert result["lead_active"] and not result["lead_saved"]
    assert result["lead_draft"]["contact_number"]["value"] == "0800000000"
    assert "could not" in result["messages"][-1].content.lower()


def test_model_cannot_reset_lead_on_a_name_reply_or_cancel_on_budget(tmp_path):
    from insurex.leads import create_lead_tool, read_leads
    class Model:
        def __init__(self, schema=None):
            self.schema = schema
        def with_structured_output(self, schema):
            return Model(schema)
        def invoke(self, messages):
            latest = next(m.content for m in reversed(messages) if isinstance(m, HumanMessage))
            if "interested" in latest:
                return LeadTurn(product_id="cheeva", product_quote="Khum Cheeva")
            if "student" in latest:
                return LeadTurn(new_customer_quote=latest, name=QuotedValue(value="Test Alpha",quote="Test Alpha"),occupation=QuotedValue(value="student",quote="student"))
            if "budget" in latest:
                return LeadTurn(action="cancel",cancel_quote=latest)
            return LeadTurn(action="detail",income=QuotedValue(value="8000 monthly",quote="income 8000 monthly"),contact_number=QuotedValue(value="0800000000",quote="0800000000"))
    db = tmp_path / "leads.sqlite"
    graph = build_graph(IndexedStore(),Model(),catalog=load_catalog(),checkpointer=InMemorySaver(),lead_tool=create_lead_tool(db))
    config = {"configurable":{"thread_id":"bad-model-actions"}}
    for question in ("I am interested in Khum Cheeva", "Test Alpha, student", "My budget is 20000 yearly"):
        result = graph.invoke({"messages":[HumanMessage(content=question)]},config)
    assert result["lead_active"] and result["lead_draft"]["product_id"] == "cheeva"
    result = graph.invoke({"messages":[HumanMessage(content="income 8000 monthly, 0800000000")]},config)
    assert result["lead_saved"]
    assert read_leads(db,"bad-model-actions")[0]["name"] == "Test Alpha"


def test_lead_connections_are_released_immediately_for_windows_cleanup(tmp_path):
    from insurex.leads import LeadRecord, create_lead_tool, read_leads
    db = tmp_path / "leads.sqlite"
    record = LeadRecord(lead_id="test",session_id="cleanup",product_id="cheeva",name="Test Alpha",occupation="student",income="8000 monthly",contact_number="0800000000",evidence={})
    create_lead_tool(db).invoke({"lead":record.model_dump()})
    assert len(read_leads(db,"cleanup")) == 1
    moved = tmp_path / "released.sqlite"
    db.rename(moved)
    assert moved.exists() and not db.exists()


@pytest.mark.parametrize("quote", ["Test Alpha, student", "a student", "budget 50 yearly", "income 30 monthly", "0800000000"])
def test_non_age_customer_information_cannot_be_rendered_as_age(quote):
    from insurex.recommendations import render_profile
    text = render_profile(CustomerNeeds(age_quote=quote),[HumanMessage(content=quote)],"English")
    assert "Age: Not verified" in text


@pytest.mark.parametrize("question", ["What if I cancel the policy after two years?", "Can I cancel this policy?", "How does cancellation work?"])
def test_policy_cancellation_questions_do_not_cancel_lead_collection(question):
    from insurex.customer_evidence import explicit_lead_cancellation
    assert not explicit_lead_cancellation("cancel" if "cancel" in question else question,question)


def test_invalid_new_age_quote_cannot_erase_previous_verified_age():
    from insurex.recommendations import merge_customer_profile
    humans = [HumanMessage(content="I'm 22, want hospital bill coverage, budget 1500 monthly"), HumanMessage(content='Budget now 900 monthly. Do not change my income or age.')]
    prior = CustomerNeeds(age_quote="I'm 22",budget_quote='budget 1500 monthly',goals=['medical'],goal_quote='hospital bill coverage',goal_is_specific=True)
    incoming = CustomerNeeds(age_quote='Do not change my income or age',budget_quote='Budget now 900 monthly')
    result = merge_customer_profile(incoming,prior.model_dump(),humans)
    assert result.age_quote == "I'm 22"
    assert result.budget_quote == 'Budget now 900 monthly'


def test_latest_explicit_budget_wins_over_stale_model_quote():
    from insurex.recommendations import merge_customer_profile
    humans = [HumanMessage(content="I'm 22. Insurance spending limit is only 1500 a month."),HumanMessage(content='Actually make the insurance budget 900 a month. Do not change my income or age.')]
    prior = CustomerNeeds(age_quote="I'm 22",budget_quote='Insurance spending limit is only 1500 a month')
    result = merge_customer_profile(prior,prior.model_dump(),humans)
    assert result.age_quote == "I'm 22"
    assert '900' in result.budget_quote and '1500' not in result.budget_quote


def test_hypothetical_budget_does_not_overwrite_actual_spending_limit():
    from insurex.recommendations import merge_customer_profile
    humans = [HumanMessage(content='My budget is 20000 yearly'),HumanMessage(content='What if my budget were 900 monthly?')]
    prior = CustomerNeeds(budget_quote='My budget is 20000 yearly')
    result = merge_customer_profile(prior,prior.model_dump(),humans)
    assert '20000' in result.budget_quote


@pytest.mark.parametrize('quote', ['Mostly protection please.', 'I mainly want protection', 'some protection please'])
def test_unqualified_protection_cannot_be_invented_as_life_goal(quote):
    from insurex.recommendations import reconcile_known_details
    result = reconcile_known_details(CustomerNeeds(goals=['life'],goal_quote=quote,goal_is_specific=True),[HumanMessage(content=quote)])
    assert result.goals == [] and not result.goal_is_specific


@pytest.mark.parametrize('quote', ['This is not a new customer.', 'Same customer, just correcting the budget.', 'ไม่ใช่ลูกค้าคนใหม่ เป็นลูกค้าคนเดิม'])
def test_negated_customer_change_cannot_erase_profile(quote):
    from insurex.customer_evidence import explicit_customer_change
    assert not explicit_customer_change(quote,quote)


@pytest.mark.parametrize('quote', ["Please don't cancel the lead.", 'Do not stop collecting my details.', 'อย่าหยุดเก็บข้อมูล'])
def test_negated_cancellation_keeps_lead_active(quote):
    from insurex.customer_evidence import explicit_lead_cancellation
    assert not explicit_lead_cancellation(quote,quote)


def test_explicit_loss_of_coverage_replaces_stale_employer_quote():
    from insurex.recommendations import merge_customer_profile
    humans = [HumanMessage(content='My employer now covers hospital bills'),HumanMessage(content='I left that company, so I have no cover now. Keep my age and budget.')]
    prior = CustomerNeeds(existing_coverage_quote='My employer now covers hospital bills',coverage_status='current')
    result = merge_customer_profile(prior,prior.model_dump(),humans)
    assert result.coverage_status == 'none'
    assert result.existing_coverage_quote == 'no cover now'


def test_single_benefit_gap_does_not_remove_all_existing_insurance():
    from insurex.recommendations import merge_customer_profile
    humans = [HumanMessage(content='My employer covers hospital bills'),HumanMessage(content='I have no cover for dental. What other insurance is suitable?')]
    prior = CustomerNeeds(existing_coverage_quote='My employer covers hospital bills',coverage_status='current')
    result = merge_customer_profile(prior,prior.model_dump(),humans)
    assert result.coverage_status == 'current'


def test_vague_children_event_cannot_become_just_another_shortlist():
    from insurex.recommendations import merge_customer_profile, render_recommendation
    humans = [HumanMessage(content='age 22 budget 20000 yearly. I want 1 million if I die.'),HumanMessage(content='I have two children. I want them to have money if something happens to me')]
    prior = CustomerNeeds(age_quote='age 22',budget_quote='budget 20000 yearly',goals=['life'],goal_quote='I want 1 million if I die',goal_is_specific=True,benefit_quote='1 million if I die')
    result = merge_customer_profile(prior,prior.model_dump(),humans)
    text = render_recommendation(result,load_catalog(),humans,[],'English')
    assert all(value in text for value in ('22','20000','1 million','disabled or ill'))


@pytest.mark.parametrize('budget', ['budget 20000', 'งบ 20000 บาท'])
def test_budget_amount_without_frequency_is_incomplete(budget):
    from insurex.recommendations import reconcile_known_details
    result = reconcile_known_details(CustomerNeeds(budget_quote=budget),[HumanMessage(content=budget)])
    assert result.budget_quote == budget and 'budget_frequency' in result.missing_details


@pytest.mark.parametrize('budget', ['500 monthly', '20000 yearly', '20000 p.a.', '2000/mo', 'งบปีละ 20000', 'งบเดือนละ 1500'])
def test_explicit_budget_frequency_does_not_need_repeating(budget):
    from insurex.recommendations import reconcile_known_details
    result = reconcile_known_details(CustomerNeeds(budget_quote=budget),[HumanMessage(content=budget)])
    assert 'budget_frequency' not in result.missing_details


@pytest.mark.parametrize('quote,text,age', [("I'm 87","I'm 87, budget 50000 yearly",87),('I am 65','I am 65, yearly budget 50000',65),('age 8','My child is age 8.',8),('eighty-seven',"I'm eighty-seven and need life cover",87),('twenty two','just turned twenty two',22)])
def test_age_check_allows_normal_sentence_punctuation(quote,text,age):
    from insurex.eligibility import confirmed_integer_age
    assert confirmed_integer_age(quote,[HumanMessage(content=text)])==age


@pytest.mark.parametrize('age,goal,expected', [(87,'life',[]),(65,'critical_illness',['cheeva']),(8,'medical',[]),(57,'retirement',['bamnan'])])
def test_age_filter_excludes_published_inapplicable_options(age,goal,expected):
    from insurex.eligibility import age_filtered_candidates
    from insurex.comparison import page_evidence
    store=IndexedStore()
    pages=page_evidence(list(store.docs.values()))
    sources=[{'id':i,'file':p.metadata['source'],'page':p.metadata['page']} for i,p in enumerate(pages,1)]
    ids={'life':['cheeva','ci_plus'],'critical_illness':['ci_plus','cheeva'],'medical':['raksa'],'retirement':['bamnan']}[goal]
    selected,variants,notes=age_filtered_candidates(ids,load_catalog(),[HumanMessage(content=f'Age {age}, premium budget 50000 yearly')],f'Age {age}',sources,'English')
    assert selected==expected and notes
    if age==57:
        assert variants['bamnan']==['85/65']
