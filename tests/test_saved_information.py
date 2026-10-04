"""Saved views use temporary synthetic databases; no API requests."""
import hashlib
import sqlite3
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from langchain_core.messages import HumanMessage, AIMessage
from insurex.config import ROOT
from insurex.web_service import ChatService, web_settings
from insurex.saved_information import read_saved_session
from insurex.lead_storage import read_leads
from insurex.leads import LeadRecord, create_lead_tool


@pytest.fixture
def saved_env(monkeypatch, tmp_path):
    monkeypatch.setenv('INSUREX_UI_STORAGE_DIR', str(tmp_path))
    monkeypatch.setenv('INSUREX_UI_OFFLINE','1')
    return tmp_path


def save_lead(directory, session, name='Demo Customer', phone='0800000000'):
    record = LeadRecord(lead_id='lead-'+session, session_id=session, product_id='cheeva',
                         name=name, occupation='student', income='20000 THB per month', contact_number=phone,
                         evidence={'name':name,'occupation':'student','income':'20000 THB per month','contact_number':phone})
    create_lead_tool(directory/'leads.sqlite').invoke({'lead':record.model_dump()})
    return record


def seed_session(session_id='customer-a'):
    adapter = ChatService(web_settings(), offline=True)
    adapter.send(session_id,'What products are available?')
    with adapter.graph() as graph:
        graph.update_state(adapter.config(session_id), {'messages':[
            HumanMessage(content='Age 22, budget 50000 THB per year, main goal life protection.'),
            AIMessage(content='Synthetic saved reply.')],
            'customer_profile':{'age_quote':'Age 22','budget_quote':'50000 THB per year','goal_quote':'life protection'},
            'lead_active':True})
    return adapter


def test_saved_session_matches_checkpoint_without_changing_database(saved_env):
    adapter = seed_session()
    expected = adapter.history('customer-a')
    database = saved_env/'sessions.sqlite'
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    restored = read_saved_session(database,'customer-a')
    assert restored['messages'] == expected['messages']
    assert restored['customer_profile'] == expected['customer_profile']
    assert restored['lead_active'] is True
    assert read_saved_session(database,"customer-a' OR 1=1 --") == {}
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before


def test_readers_handle_missing_or_uninitialized_databases_without_creating_files(saved_env):
    missing = saved_env/'missing.sqlite'
    assert read_saved_session(missing,'anything') == {}
    assert read_leads(missing) == []
    assert not missing.exists()
    with sqlite3.connect(missing):
        pass
    assert read_saved_session(missing,'anything') == {}
    assert read_leads(missing) == []


def test_all_leads_and_session_filter_are_read_only_and_instance_scoped(saved_env):
    save_lead(saved_env,'a')
    save_lead(saved_env,'b',name='Second Customer',phone='0811111111')
    other = saved_env/'other-instance'
    other.mkdir()
    save_lead(other,'c',name='Other Instance Customer')
    database = saved_env/'leads.sqlite'
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    assert len(read_leads(database)) == 2
    assert [r['name'] for r in read_leads(database,'a')] == ['Demo Customer']
    assert read_leads(database,"a' OR 1=1 --") == []
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before


def test_saved_view_resumes_selected_conversation_and_retains_profile(saved_env):
    seed_session()
    ui = AppTest.from_file(str(ROOT/'app.py'),default_timeout=20).run()
    ui.radio(key='view').set_value('Saved information').run()
    assert not ui.exception
    assert any(title.value == 'Saved information' for title in ui.title)
    assert not ui.chat_input
    ui.selectbox(key='saved_conversation').select('customer-a').run()
    assert not ui.exception
    assert len(ui.chat_message) == 4
    assert '50000 THB per year' in str(ui.table[0].value)
    assert any('unfinished' in item.value for item in ui.info)
    ui.button(key='resume_saved').click().run()
    assert not ui.exception
    assert ui.session_state.view == 'Chat'
    assert ui.session_state.conversation == 'customer-a'
    assert len(ui.chat_message) == 4
    assert ui.chat_input


def test_leads_view_searches_filters_and_opens_correct_chat(saved_env):
    seed_session('a')
    seed_session('b')
    save_lead(saved_env,'a')
    save_lead(saved_env,'b',name='Second Customer',phone='0811111111')
    ui = AppTest.from_file(str(ROOT/'app.py'),default_timeout=20).run()
    ui.radio(key='view').set_value('Saved information').run()
    assert not ui.exception
    assert len(ui.dataframe[0].value) == 2
    assert ui.dataframe[0].value.iloc[0]['Phone'] == '0800000000'
    ui.selectbox(key='selected_lead').select('lead-b').run()
    ui.text_input(key='lead_search').set_value('0800000000').run()
    assert not ui.exception
    assert ui.selectbox(key='selected_lead').value == 'lead-a'
    assert 'Demo Customer' in str(ui.table[0].value)
    ui.text_input(key='lead_search').set_value('').run()
    ui.selectbox(key='lead_session_filter').select('b').run()
    assert list(ui.dataframe[0].value['Name']) == ['Second Customer']
    ui.text_input(key='lead_search').set_value('0800000000').run()
    assert not ui.dataframe
    assert any('No leads match' in item.value for item in ui.info)
    ui.text_input(key='lead_search').set_value('').run()
    ui.button(key='open_lead_chat').click().run()
    assert not ui.exception
    assert ui.session_state.view == 'Chat'
    assert ui.session_state.conversation == 'b'
    ui.radio(key='view').set_value('Saved information').run()
    ui.radio(key='view').set_value('Chat').run()
    assert ui.session_state.conversation == 'b'
    ui.radio(key='view').set_value('Saved information').run()
    ui.button(key='new_chat').click().run()
    assert ui.session_state.view == 'Chat'
    assert ui.session_state.conversation != 'b'
    assert not ui.chat_message


def test_saved_view_does_not_initialize_model_or_index_without_api_key(saved_env,monkeypatch):
    import insurex.web_service as adapter
    monkeypatch.setenv('INSUREX_UI_OFFLINE','0')
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    def forbidden(*args,**kwargs):
        raise AssertionError('Saved view must not initialize a model/index service')
    monkeypatch.setattr(adapter,'ChatService',forbidden)
    ui = AppTest.from_file(str(ROOT/'app.py'),default_timeout=20)
    ui.session_state.conversation = 'not-saved'
    ui.session_state.view = 'Saved information'
    ui.run()
    assert not ui.exception
    assert not ui.error
    assert any('No conversations saved' in item.value for item in ui.info)
    assert any('No completed leads' in item.value for item in ui.info)
    assert not ui.chat_input
