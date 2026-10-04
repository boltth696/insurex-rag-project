"""Simple local conversations and completed-leads view."""
import json
import logging
import streamlit as st
from .config import ROOT
from .sessions import list_sessions
from .lead_storage import read_leads
from .saved_information import read_saved_session, remembered_details
from .web_service import visible_messages


def render_saved_information(settings, on_resume):
    st.title("Saved information")
    st.caption("Browse conversations and completed leads saved in this instance.")
    try:
        sessions = list_sessions(settings.session_db)
        leads = read_leads(settings.lead_db)
    except Exception:
        logging.exception("Could not read saved information")
        st.error("Saved information could not be opened. Your records have not been changed.")
        return
    st.caption(f"{len(sessions)} saved conversations · {len(leads)} completed leads")
    st.button("Refresh saved information", key="refresh_saved")
    customer_names = {r['session_id']:r['name'] for r in leads}
    conversations_tab, leads_tab = st.tabs(["Conversations", "Leads"])
    with conversations_tab:
        if not sessions:
            st.info("No conversations saved yet. Start a chat to create one.")
        else:
            selected = st.selectbox("Saved conversation", sessions, index=None,
                                    placeholder="Choose a conversation", key="saved_conversation",
                                    format_func=lambda value: value + (' · ' + customer_names[value] if value in customer_names else ''))
            if selected:
                try:
                    snapshot = read_saved_session(settings.session_db, selected)
                    st.button("Resume this conversation", key="resume_saved", type="primary",
                              on_click=on_resume, args=(selected,))
                    details = remembered_details(snapshot)
                    if details:
                        st.subheader("Remembered customer details")
                        st.table(details)
                    if snapshot.get("lead_active"):
                        st.info("Contact collection is unfinished. Resume this conversation to complete it.")
                    st.subheader("Conversation history")
                    messages = visible_messages(snapshot)
                    if not messages:
                        st.info("This conversation has no saved chat messages.")
                    for role, text in messages:
                        with st.chat_message(role):
                            st.markdown(text)
                except Exception:
                    logging.exception("Could not read saved conversation")
                    st.error("This conversation could not be opened. Its saved data has not been changed.")
    with leads_tab:
        if not leads:
            st.info("No completed leads yet. Tell the assistant you are interested in a product, then provide the requested contact details.")
            return
        search = st.text_input("Search name, phone or product", key="lead_search").strip().casefold()
        lead_sessions = sorted({r['session_id'] for r in leads})
        selected_session = st.selectbox("Conversation filter", [None] + lead_sessions,
                                         format_func=lambda value: "All conversations" if value is None else value,
                                         key="lead_session_filter")
        products = json.loads((ROOT / "data/product_catalog.json").read_text(encoding="utf-8"))["products"]
        names = {p['id']:p['name_en'] for p in products}
        displayed = []
        for record in leads:
            if selected_session is not None and record['session_id'] != selected_session:
                continue
            searchable = ' '.join(str(record.get(k,'')) for k in ('name','contact_number','product_id')) + ' ' + names.get(record['product_id'],'')
            if search and search not in searchable.casefold():
                continue
            displayed.append(record)
        if not displayed:
            st.info("No leads match these filters.")
            return
        st.caption(f"Showing {len(displayed)} completed leads")
        rows = [{"Name":r['name'], "Phone":r['contact_number'],
                 "Product":names.get(r['product_id'],r['product_id'])} for r in displayed]
        st.dataframe(rows, hide_index=True, width="stretch")
        st.download_button("Download displayed leads", json.dumps(displayed,ensure_ascii=False,indent=2),
                           file_name="insurex-leads.json", mime="application/json", on_click="ignore", key="download_leads")
        by_id = {r['lead_id']:r for r in displayed}
        if st.session_state.get('selected_lead') not in by_id:
            st.session_state.pop('selected_lead', None)
        selected_lead = st.selectbox("Lead details", list(by_id), key="selected_lead",
                                      format_func=lambda value: f"{by_id[value]['name']} · {names.get(by_id[value]['product_id'],by_id[value]['product_id'])} · {by_id[value]['contact_number']}")
        record = by_id[selected_lead]
        st.table([{'Detail':label,'Saved value':str(value)} for label,value in [
            ('Name',record['name']),('Occupation',record['occupation']),('Income',record['income']),
            ('Phone',record['contact_number']),('Product',names.get(record['product_id'],record['product_id'])),
            ('Conversation',record['session_id'])]])
        st.button("Open this lead's conversation", key="open_lead_chat", on_click=on_resume,
                  args=(record['session_id'],), disabled=record['session_id'] not in sessions)
        with st.expander("Original customer statements"):
            for field, quote in record.get('evidence',{}).items():
                st.caption(field.replace('_',' ').title())
                st.text(quote)
