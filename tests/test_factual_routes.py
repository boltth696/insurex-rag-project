import subprocess
import pytest
from insurex.catalog import catalog_intent, load_catalog
from insurex.comparison import comparison_intent
from insurex.graph import reviewed_payment_example
from insurex.ingestion import load_pages
from insurex.graph import build_graph, GroundedAnswer, FollowupDecision
from langchain_core.messages import HumanMessage
from tests.test_benefits import IndexedStore


@pytest.mark.parametrize('question', [
    "What minimum sums insured are listed for CI Plus's five-, ten- and twenty-year payment options?",
    'What minimum sum assured does CI Plus require for five-year payments?',
    'Do CI 50 rider premiums automatically stop after the base ten years?',
    'Is age 60 eligible for the twenty-year option of CI Plus?',
    'Does Khum Bamnan always require ten years of premiums?',
])
def test_detailed_questions_bypass_simple_catalog(question):
    assert catalog_intent(question, load_catalog()) is None
    assert comparison_intent(question) != 'payment_rank'


@pytest.mark.parametrize('plan,insured,short,long', [
    (1,'200,000','25,400','7,200'), (2,'500,000','63,500','18,000'),
    (3,'800,000','101,600','28,800'), (4,'1,000,000','127,000','36,000'),
])
def test_requested_plan_keeps_its_own_example(plan, insured, short, long):
    text = reviewed_payment_example(f'CI Plus Plan {plan} five-year versus twenty-year premiums', [{'id':2,'file':'11_test.pdf','page':2}], 'English')
    assert f'Plan {plan}' in text
    assert all(value in text for value in (insured,short,long))
    assert 'not quotes' in text


def test_pdf_worker_retry_contains_native_crash(monkeypatch, tmp_path):
    from insurex import ingestion
    (tmp_path / 'sample.pdf').write_bytes(b'fake PDF for mocked worker')
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, -1073741819 if len(calls) == 1 else 0, stdout=b'["page one"]')
    monkeypatch.setattr(ingestion.subprocess, 'run', run)
    pages, report = load_pages(tmp_path)
    assert len(calls) == 2 and pages[0].page_content == 'page one'
    assert pages[0].metadata['page'] == 1
    assert report[0]['pages'][0]['characters'] == 8


def test_repeated_native_crash_does_not_index_empty_result(monkeypatch, tmp_path):
    from insurex import ingestion
    (tmp_path / 'sample.pdf').write_bytes(b'fake PDF')
    monkeypatch.setattr(ingestion.subprocess, 'run', lambda command, **kw: subprocess.CompletedProcess(command, 3221225477, stdout=b''))
    with pytest.raises(ValueError, match='source was not indexed'):
        load_pages(tmp_path)


def test_collapsed_worker_exit_gets_one_retry_and_useful_failure(monkeypatch,tmp_path):
    from insurex import ingestion
    (tmp_path/'sample.pdf').write_bytes(b'fake PDF')
    calls=[]
    def run(command,**kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command,1,stdout=b'',stderr=b'PdfReadError: synthetic invalid document')
    monkeypatch.setattr(ingestion.subprocess,'run',run)
    with pytest.raises(ValueError,match='PdfReadError: synthetic invalid document'):
        load_pages(tmp_path)
    assert len(calls)==2


def test_semantic_rewrite_cannot_drop_explicit_product():
    class Model:
        def __init__(self, schema=None):
            self.schema = schema
        def with_structured_output(self, schema):
            return Model(schema)
        def invoke(self, messages):
            if self.schema is FollowupDecision:
                return FollowupDecision(kind='detail',topic='cancer_payment',query='What does the hypothetical greater-of rule calculate?')
            return GroundedAnswer(supported=True,answer='Conditional example calculation',citation_ids=[2])
    state = build_graph(IndexedStore(),Model(),catalog=load_catalog()).invoke({'profile_context':True,'messages':[HumanMessage(content='Hypothetical CI Plus example: what does the greater-of rule calculate?')]})
    assert 'Khum Talodcheep CI Plus' in state['query']
    assert all(s['file'].startswith('11_') for s in state['sources'])
    assert 'Sources:' in state['messages'][-1].content


def test_partial_comparison_retries_missing_source_citations():
    class Model:
        def __init__(self):
            self.calls = 0
        def with_structured_output(self, schema):
            return self
        def invoke(self, messages):
            self.calls += 1
            return GroundedAnswer(supported=False,answer='CI Plus specifies 90 days; CI50 complete terms are unavailable.',citation_ids=[] if self.calls == 1 else [3,6])
    model = Model()
    state = build_graph(IndexedStore(),model,catalog=load_catalog()).invoke({'messages':[HumanMessage(content='Does CI Plus having a 90-day waiting period prove Cheeva CI50 has the same wait?')]})
    assert model.calls == 2
    assert '02_SCB' in state['messages'][-1].content and '11_SCB' in state['messages'][-1].content


@pytest.mark.parametrize('income,expected', [('20000 monthly',True), ('5000 yearly',False)])
def test_mixed_income_budget_quote_cannot_save_budget_as_income(income, expected):
    from insurex.leads import income_value_is_supported, QuotedValue
    assert income_value_is_supported(QuotedValue(value=income,quote='income 20000 monthly, premium budget 5000 yearly')) is expected


def test_changed_pdf_invalidates_existing_index_before_any_api_use(tmp_path):
    import hashlib
    from dataclasses import replace
    from insurex.config import Settings
    from insurex.vectorstore import save_index, load_index
    from tests.test_framework import store, OfflineEmbeddings
    pdfs = tmp_path/'pdfs'
    pdfs.mkdir()
    source = pdfs/'source.pdf'
    source.write_bytes(b'original source')
    settings = replace(Settings(),pdf_dir=pdfs,index_dir=tmp_path/'index')
    save_index(store(),settings.index_dir,{'embedding_model':settings.embedding_model,'files':[{'file':source.name,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}]})
    assert load_index(settings,OfflineEmbeddings()).index.ntotal == 2
    source.write_bytes(b'updated source')
    with pytest.raises(ValueError,match='Source PDFs changed since indexing'):
        load_index(settings)


def test_deductible_exception_preserves_minor_surgery_scope():
    from insurex.table_facts import reviewed_deductible_scope
    catalog = load_catalog()
    product = next(p for p in catalog.products if p.id=='raksa')
    sources = [{'id':3,'file':product.source_file,'page':3}]
    text = reviewed_deductible_scope('For Khum Raksa Maojai Extra, is the deductible once for the entire year or per inpatient admission? Does it apply to every benefit?',sources,catalog,'English')
    assert all(value in text for value in ('30,000','per inpatient admission','minor surgery ONLY','2.1','3.1','6.1','Sources:'))
    assert reviewed_deductible_scope('CI Plus deductible per admission?',sources,catalog,'English') is None
    assert reviewed_deductible_scope('Khum Raksa Maojai Extra deductible plan premium price?',sources,catalog,'English') is None


def test_flat_application_graph_does_not_scan_node_closure_bytecode(monkeypatch):
    from langgraph.pregel import _utils
    calls = []
    def unsupported_scan(function):
        calls.append(function)
        return []
    monkeypatch.setattr(_utils,'get_function_nonlocals',unsupported_scan)
    result = build_graph(None,None,catalog=load_catalog()).invoke({'messages':[HumanMessage(content='hello')]})
    assert result['messages'][-1].content.startswith('Hello!')
    assert not calls


def test_flat_node_forwards_session_configuration():
    from insurex.flat_node import FlatNode
    seen = []
    node = FlatNode(lambda state,config: seen.append(config['configurable']['thread_id']) or state,takes_config=True)
    assert node.invoke({'value':1},{'configurable':{'thread_id':'synthetic'}})=={'value':1}
    assert seen==['synthetic']


@pytest.mark.parametrize('question,expected', [
 ('I am 35 years old. Compare five-year and twenty-year premium payments.',[5,20]),
 ('A 35-year-old asks about ten-year versus twenty-year payments.',[10,20]),
 ('Compare five-, ten- and twenty-year premiums.',[5,10,20]),
 ('อายุ 35 ปี เปรียบเทียบเบี้ยชำระ 5 ปี กับ 20 ปี',[5,20]),
 ('Compare five-year and fifteen-year premiums.',[5,15]),
 ('A twenty-two-year-old asks about twenty-five-year premiums.',[25]),
])
def test_customer_age_is_not_a_payment_period(question,expected):
    from insurex.graph import payment_periods
    assert payment_periods(question)==expected


def test_requested_three_plan4_periods_preserve_all_annual_rates():
    text = reviewed_payment_example('CI Plus Plan 4 five-, ten- and twenty-year annual premiums',[{'id':2,'file':'11_test.pdf','page':2}],'English')
    assert all(value in text for value in ('127,000','65,000','36,000','1,000,000','not customer quotes'))


def test_named_premium_options_question_is_not_full_catalog_listing():
    assert catalog_intent('For CI Plus, compare five-year and fifteen-year premium payment options.',load_catalog()) is None
