"""Regression for a real live claim that passed citation-only checks."""
import pytest
from langchain_core.messages import HumanMessage
from insurex.catalog import load_catalog
from insurex.graph import build_graph, GroundedAnswer
from tests.test_benefits import IndexedStore, QUESTION


class Answers:
    def __init__(self, replies):
        self.replies = replies
        self.calls = 0

    def with_structured_output(self,schema):
        return self

    def invoke(self,messages):
        reply = self.replies[min(self.calls,len(self.replies)-1)]
        self.calls += 1
        return GroundedAnswer(supported=True,answer=reply,citation_ids=[2,4])


@pytest.mark.parametrize('bad',[
    'CI 50 covers 50 critical illnesses.',
    'CI 50 provides coverage for fifty diseases.',
    'CI 50 covers a broader but unspecified set of 50 illnesses.',
    'CI 50 คุ้มครองโรคร้ายแรง 50 โรค',
])
def test_citations_cannot_validate_a_count_inferred_from_a_rider_name(bad):
    model = Answers([bad])
    state = build_graph(IndexedStore(),model,catalog=load_catalog()).invoke({'messages':[HumanMessage(content=QUESTION)]})
    assert model.calls == 2
    assert 'Unsupported CI 50' in state['error']
    assert 'could not find enough' in state['messages'][-1].content
    assert 'Sources:' not in state['messages'][-1].content


def test_unsupported_count_can_be_repaired_without_losing_supported_facts():
    good = 'CI 50 full illness definitions are not established here. CI Plus covers 15 severe and 4 early-stage illnesses.'
    model = Answers(['CI 50 covers 50 illnesses.',good])
    state = build_graph(IndexedStore(),model,catalog=load_catalog()).invoke({'messages':[HumanMessage(content=QUESTION)]})
    assert model.calls == 2
    assert state['error'] == ''
    assert good in state['messages'][-1].content
    assert '02_SCB' in state['messages'][-1].content and '11_SCB' in state['messages'][-1].content


def test_explicit_limitations_and_supported_ci_plus_counts_are_retained():
    good = 'I cannot infer that CI 50 covers 50 illnesses from its name. CI Plus covers 15 severe and 4 early-stage illnesses.'
    model = Answers([good])
    state = build_graph(IndexedStore(),model,catalog=load_catalog()).invoke({'messages':[HumanMessage(content=QUESTION)]})
    assert model.calls == 1
    assert state['error'] == ''
    assert good in state['messages'][-1].content


def test_universal_pension_term_question_receives_an_interpreted_answer():
    class Model(Answers):
        def invoke(self,messages):
            self.calls += 1
            return GroundedAnswer(supported=True,answer='No. Premiums are paid until age 55, so the duration depends on entry age.',citation_ids=[4])
    model = Model([])
    state = build_graph(IndexedStore(),model,catalog=load_catalog()).invoke({'messages':[HumanMessage(content='For Khum Bamnan 85/55, does everyone pay premiums for exactly 10 years?')]})
    assert model.calls == 1
    assert state['mode'] == 'single'
    assert state['messages'][-1].content.startswith('No.')
    assert 'entry age' in state['messages'][-1].content
    assert '05_SCB' in state['messages'][-1].content
