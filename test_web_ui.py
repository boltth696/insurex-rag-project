"""Browser UI persistence and failure paths, without API calls or real records."""
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from insurex.config import ROOT
from insurex.web_service import ChatService, web_settings


@pytest.fixture
def ui_env(monkeypatch, tmp_path):
    monkeypatch.setenv("INSUREX_UI_STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("INSUREX_UI_OFFLINE", "1")
    return tmp_path


def test_chat_ui_sends_once_restores_and_separates_conversations(ui_env):
    ui = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
    assert not ui.exception
    first_id = ui.session_state.conversation
    ui.chat_input[0].set_value("What products are available?").run()
    assert not ui.exception
    assert len(ui.chat_message) == 2
    assert "Cheeva" in ui.chat_message[1].markdown[0].value
    ui.run()
    assert len(ui.chat_message) == 2  # reruns must not repeat requests
    ui.button(key="new_chat").click().run()
    assert not ui.exception
    assert ui.session_state.conversation != first_id
    assert len(ui.chat_message) == 0
    ui.selectbox(key="conversation_picker").select(first_id).run()
    assert len(ui.chat_message) == 2
    # A fresh browser/service connection recovers the same persisted history.
    restored = ChatService(web_settings(), offline=True)
    assert len(restored.history(first_id)["messages"]) == 2
    assert restored.sessions() == [first_id]


def test_ui_startup_error_has_no_traceback_or_enabled_input(ui_env, monkeypatch):
    import insurex.web_service as adapter
    monkeypatch.setenv("INSUREX_UI_OFFLINE", "0")
    monkeypatch.setattr(adapter, "require_api_key", lambda: (_ for _ in ()).throw(ValueError("Add OPENAI_API_KEY to .env before ingesting or chatting.")))
    ui = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
    assert not ui.exception
    assert "could not start" in ui.error[0].value
    assert not ui.chat_input


def test_ui_request_error_does_not_show_success_or_store_message(ui_env):
    ui = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
    ui.chat_input[0].set_value("/exit").run()
    assert not ui.exception
    assert "New conversation" in ui.error[0].value
    ui.run()
    assert not ui.chat_message
    assert ui.warning
    ui.button(key="new_chat").click().run()
    assert not ui.warning


def test_web_adapter_rejects_empty_session_or_message(ui_env):
    adapter = ChatService(web_settings(), offline=True)
    with pytest.raises(ValueError, match="conversation ID"):
        adapter.history("")
    with pytest.raises(ValueError, match="message"):
        adapter.send("test", "  ")
    with pytest.raises(ValueError, match="message"):
        adapter.send("test", "x" * 6001)


def test_online_ui_lead_collection_persists_across_reruns(ui_env, monkeypatch):
    import insurex.web_service as adapter
    from tests.test_leads import Model, INTEREST, DETAILS, PHONE
    from tests.test_benefits import IndexedStore
    from insurex.lead_storage import read_leads
    original = adapter.ChatService
    def synthetic_service(settings, offline):
        result = original(settings, offline=True)
        result.offline = offline
        if not offline:
            result.model, result.store = Model(), IndexedStore()
        return result
    monkeypatch.setattr(adapter, "ChatService", synthetic_service)
    monkeypatch.setenv("INSUREX_UI_OFFLINE", "0")
    ui = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
    session_id = ui.session_state.conversation
    for question in [INTEREST, DETAILS, PHONE]:
        ui.chat_input[0].set_value(question).run()
        assert not ui.exception
    assert "saved to the local database" in ui.chat_message[-1].markdown[0].value
    records = read_leads(ui_env / "leads.sqlite", session_id)
    assert len(records) == 1
    assert records[0]["name"] == "Demo Customer"
    assert records[0]["income"] == "30000 THB per month"
    ui.run()
    assert len(read_leads(ui_env / "leads.sqlite", session_id)) == 1
