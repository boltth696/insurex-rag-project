"""Run with: python -m streamlit run app.py"""
from datetime import datetime
from uuid import uuid4
import os
import logging
import streamlit as st
from insurex.web_service import ChatService, web_settings, visible_messages

st.set_page_config(page_title="InsureX · Insurance Assistant", page_icon="💬", layout="centered")
st.markdown("""<style>
[data-testid="stChatMessage"] p, [data-testid="stChatMessage"] li {
    font-size: 1.05rem; line-height: 1.7;
}
[data-testid="stChatMessage"] { padding: 1rem; }
</style>""", unsafe_allow_html=True)


@st.cache_resource
def service(settings, offline):
    return ChatService(settings, offline)


def new_conversation():
    st.session_state.conversation = "web-" + datetime.now().strftime("%Y%m%d-%H%M") + "-" + uuid4().hex[:6]
    st.session_state.view = "Chat"
    st.session_state.pop("conversation_picker", None)
    st.session_state.pop("last_error", None)


def clear_error():
    st.session_state.pop("last_error", None)


def resume_conversation(session_id):
    st.session_state.conversation = session_id
    st.session_state.view = "Chat"
    st.session_state.pop("conversation_picker", None)
    clear_error()


def choose_conversation():
    st.session_state.conversation = st.session_state.conversation_picker
    clear_error()


if "conversation" not in st.session_state:
    new_conversation()

with st.sidebar:
    st.title("InsureX")
    st.caption("Your insurance conversation")
    st.button("＋ New conversation", key="new_chat", on_click=new_conversation, type="primary", width="stretch")
    st.radio("View", ["Chat", "Saved information"], key="view", on_change=clear_error)
    mode = st.radio("Chat mode", ["Online assistant", "Offline catalog"],
                    index=1 if os.getenv("INSUREX_UI_OFFLINE") == "1" else 0, on_change=clear_error,
                    help="Online uses your configured API credit. Offline supports basic product listings and payment terms.")

try:
    settings = web_settings()
except Exception:
    logging.exception("Could not load local configuration")
    st.error("The project configuration could not be loaded. Check your settings and reopen the app.")
    st.stop()

if st.session_state.view == "Saved information":
    from insurex.saved_ui import render_saved_information
    render_saved_information(settings, resume_conversation)
    st.stop()

try:
    assistant = service(settings, mode == "Offline catalog")
    sessions = assistant.sessions()
    choices = list(dict.fromkeys([st.session_state.conversation] + sessions))
    with st.sidebar:
        # Keep the active ID outside widget state: Streamlit removes hidden
        # widgets when switching to the Saved information view.
        st.selectbox("Conversation", choices, key="conversation_picker", on_change=choose_conversation)
        st.caption("Conversations are saved on this computer. Select an ID to resume it.")
        st.divider()
        st.caption("Interested in a product? Tell the assistant to start collecting your contact details.")
        st.caption("Local app · English and Thai")
    state = assistant.history(st.session_state.conversation)
except Exception as exc:
    logging.exception("Could not open local chat")
    st.title("Insurance Assistant")
    st.error("The chatbot could not start. Check the project configuration, then reopen the app.")
    if isinstance(exc, ValueError):
        st.caption(str(exc))
    st.stop()

st.title("Insurance Assistant")
st.caption("Explore the supplied brochures, compare protection, and ask follow-up questions.")
if mode == "Offline catalog":
    st.info("Offline catalog mode: basic product information only. Switch to Online assistant for recommendations and lead collection.")

history = visible_messages(state)
if not history:
    st.subheader("How can I help?")
    st.write("Ask about a product, or tell me your age, budget and what you want to protect.")
    st.caption('For example: “What products are available?” or “I’m 22, with ฿20,000 per year for life protection.”')
for role, content in history:
    with st.chat_message(role):
        st.markdown(content)
if state.get("lead_active"):
    st.caption("Contact collection in progress. Type /cancel-lead to cancel.")
if st.session_state.get("last_error"):
    st.warning(st.session_state.last_error)

question = st.chat_input("Ask in English or Thai…", max_chars=6000, key="message", submit_mode="disable")
if question:
    with st.chat_message("user"):
        st.markdown(question)
    try:
        with st.spinner("Reading your question…"):
            result = assistant.send(st.session_state.conversation, question)
        st.session_state.last_error = ("Some information could not be verified. Please check the limitations in the answer or ask a more specific question."
                                       if result.get("error") else "")
        st.rerun()
    except Exception as exc:
        logging.exception("Local chat request failed")
        st.session_state.last_error = (str(exc) if isinstance(exc, ValueError) else
                                      "Your message could not be completed. Try again, or reopen the app if it has disconnected.")
        st.error(st.session_state.last_error)
