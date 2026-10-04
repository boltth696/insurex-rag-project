"""Authorized synthetic live variations, isolated from customer databases."""
import argparse
import json
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from insurex.config import Settings, ROOT, require_api_key
from insurex.catalog import load_catalog
from insurex.vectorstore import load_index
from insurex.graph import build_graph
from insurex.leads import create_lead_tool, read_leads


def check(state, spec, saved):
    errors = []
    text = str(state["messages"][-1].content).lower()
    if state.get("error"):
        errors.append(state["error"])
    for word in spec.get("contains", []):
        if word.lower() not in text:
            errors.append("Missing answer fragment: " + word)
    for word in spec.get("absent", []):
        if word.lower() in text:
            errors.append("Unwanted answer fragment: " + word)
    for alternatives in spec.get("contains_any", []):
        if not any(word.lower() in text for word in alternatives):
            errors.append("Missing any answer fragment: " + ", ".join(alternatives))
    for prefix in spec.get("source_prefixes", []):
        if prefix.lower() not in text:
            errors.append("Missing cited brochure: " + prefix)
    for key in ("mode", "lead_active", "lead_saved"):
        if key in spec and state.get(key, False) != spec[key]:
            errors.append(f"{key} expected {spec[key]}, got {state.get(key)}")
    for field, value in spec.get("profile", {}).items():
        actual = state.get("customer_profile", {}).get(field, "")
        if value == "" and actual or value != "" and value.lower() not in str(actual).lower():
            errors.append(f"profile.{field}: expected {value}, got {actual}")
    for field, value in spec.get("draft", {}).items():
        entry = state.get("lead_draft", {}).get(field, {})
        actual = entry.get("value", "") if isinstance(entry, dict) else entry
        if value.lower() not in actual.lower():
            errors.append(f"draft.{field}: expected {value}, got {actual}")
    if spec.get("income_empty") and state.get("lead_draft", {}).get("income"):
        errors.append("Premium budget became income")
    for field, value in spec.get("saved", {}).items():
        if not saved or saved[-1].get(field) != value:
            errors.append(f"Saved {field} did not match expected value")
    return errors


def main():
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", nargs="*", help="Selected case names, all by default")
    parser.add_argument("--tag", default="initial")
    parser.add_argument("--case-file", default="variation_cases.json", help="Case JSON filename under demo/")
    args = parser.parse_args()
    settings = Settings.load()
    require_api_key()
    if Path(args.case_file).name != args.case_file or Path(args.tag).name != args.tag:
        parser.error("Case file and tag must be plain filenames.")
    specs = json.loads((ROOT / "demo" / args.case_file).read_text(encoding="utf-8"))
    cases = args.cases or list(specs)
    output = ROOT / "demo" / ("variations-" + args.tag + ".json")
    records = []
    (ROOT / "work").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="insurex-variation-", dir=ROOT / "work") as temporary:
        db = Path(temporary) / "leads.sqlite"
        graph = build_graph(load_index(settings), ChatOpenAI(model=settings.chat_model, temperature=0, timeout=45, max_retries=1), catalog=load_catalog(), checkpointer=InMemorySaver(), lead_tool=create_lead_tool(db))
        for case in cases:
            config = {"configurable": {"thread_id": "variation-" + case}}
            for i, spec in enumerate(specs[case], 1):
                state = graph.invoke({"messages": [HumanMessage(content=spec["q"])]}, config)
                saved = read_leads(db, "variation-" + case)
                issues = check(state, spec, saved)
                records.append({"case": case, "turn": i, "question": spec["q"], "answer": str(state["messages"][-1].content), "mode": state["mode"], "topic": state.get("answer_topic"), "profile": state.get("customer_profile", {}), "lead_draft": state.get("lead_draft", {}), "lead_active": state.get("lead_active", False), "lead_saved": state.get("lead_saved", False), "saved": saved, "issues": issues})
                output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"{case} {i}: {'PASS' if not issues else 'FAIL ' + '; '.join(issues)}", flush=True)
    print(f"{sum(not r['issues'] for r in records)}/{len(records)} targeted checks passed; {output.name}", flush=True)


if __name__ == "__main__":
    main()
