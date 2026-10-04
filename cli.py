import argparse
import sys
import json
from pathlib import Path
from dataclasses import replace
from .config import Settings, require_api_key


def main():
    parser = argparse.ArgumentParser(description="InsureX PDF assistant")
    parser.add_argument("command", choices=["inspect", "ingest", "chat", "verify-catalog", "leads", "sessions"])
    parser.add_argument("--offline", action="store_true", help="Use reviewed catalog answers locally without an API key")
    parser.add_argument("--session", default="demo-user-1", help="Conversation ID; use distinct IDs for distinct conversations")
    parser.add_argument("--storage-dir", type=Path, help="Optional separate directory for session/lead databases; brochure index stays unchanged")
    args = parser.parse_args()
    try:
        settings = Settings.load()
        if args.storage_dir is not None:
            directory = args.storage_dir.resolve()
            settings = replace(settings,session_db=directory/'sessions.sqlite',lead_db=directory/'leads.sqlite')
        if args.command == "sessions":
            from .sessions import list_sessions
            sessions = list_sessions(settings.session_db)
            print(f"Saved sessions: {len(sessions)}")
            for session in sessions:
                print(session)
            return
        if args.command == "leads":
            from .lead_storage import read_leads
            records = read_leads(settings.lead_db, args.session)
            print(json.dumps(records, ensure_ascii=False, indent=2))
            return
        if args.command == "inspect":
            from .ingestion import inspect_pdfs
            report, target = inspect_pdfs(settings)
            for item in report:
                pages = item["pages"]
                print(f"{item['file']}: {len(pages)} pages, {sum(p['characters'] for p in pages)} characters, {sum(p['thai_characters'] for p in pages)} Thai characters")
                for page in pages:
                    if page["characters"] < 30:
                        print(f"  WARNING: page {page['page']} may require OCR")
            print(f"Report: {target}")
            return
        if args.command == "verify-catalog":
            from .catalog import load_catalog, verify_catalog_evidence
            from .ingestion import load_pages
            catalog = load_catalog(pdf_dir=settings.pdf_dir)
            pages, _ = load_pages(settings.pdf_dir)
            verify_catalog_evidence(catalog, pages)
            print(f"Verified {len(catalog.products)} products against PDF hashes and cited source pages.")
            return
        if args.command == "ingest":
            require_api_key()
            from .vectorstore import build_index
            pages, chunks = build_index(settings)
            print(f"Indexed {pages} pages as {chunks} chunks in {settings.index_dir}", flush=True)
            return
        from .catalog import load_catalog
        from .graph import build_graph
        from .leads import create_lead_tool
        from langchain_core.messages import HumanMessage
        from langgraph.checkpoint.sqlite import SqliteSaver
        catalog = load_catalog(pdf_dir=settings.pdf_dir)
        if not args.offline:
            require_api_key()
            from .vectorstore import load_index
            from langchain_openai import ChatOpenAI
        store = None if args.offline else load_index(settings)
        settings.session_db.parent.mkdir(parents=True, exist_ok=True)
        model = None if args.offline else ChatOpenAI(model=settings.chat_model, temperature=0, timeout=60, max_retries=2)
        with SqliteSaver.from_conn_string(str(settings.session_db)) as saver:
            graph = build_graph(store, model, settings.top_k, saver, catalog=catalog, lead_tool=None if args.offline else create_lead_tool(settings.lead_db))
            config = {"configurable": {"thread_id": args.session}}
            print(f"Session: {args.session}. Type /exit to quit. Existing session history is restored.")
            while True:
                question = input("You: ").strip()
                if question.lower() == "/exit":
                    break
                if not question:
                    continue
                state = graph.invoke({"messages": [HumanMessage(content=question)]}, config)
                print("Assistant:", state["messages"][-1].content)
                if state.get("error"):
                    print(state["error"], file=sys.stderr)
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye.")
    except Exception as exc:
        print(f"Error ({type(exc).__name__}): {exc}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
