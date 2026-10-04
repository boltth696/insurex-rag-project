"""Record an actual synthetic RAG/lead/session demo in isolated SQLite storage.

Default mode is offline and makes no API calls. --live exercises extraction
and detailed answers with the configured OpenAI models and supplied brochures.
No existing session or lead databases are read. Logs contain synthetic data.
"""
import argparse
from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def history_probe(directory, session):
    from insurex.config import Settings
    from insurex.web_service import ChatService, visible_messages
    settings = replace(Settings(), session_db=directory/'sessions.sqlite', lead_db=directory/'leads.sqlite')
    state = ChatService(settings, offline=True).history(session)
    return {'history':visible_messages(state), 'profile':state.get('customer_profile',{}),
            'lead_active':state.get('lead_active',False), 'lead_draft':state.get('lead_draft',{})}


def write_log(directory, records, mode, model, metadata=None):
    directory.mkdir(parents=True, exist_ok=True)
    report = {'recorded_at':datetime.now(ZoneInfo('Asia/Bangkok')).isoformat(),
              'mode':mode, 'chat_model':model if mode == 'live' else None,
              'synthetic_data_only':True, 'storage':'temporary isolated SQLite; removed after the run',
              'records':records,
              'passed':sum(not r['issues'] for r in records), 'total':len(records)}
    if metadata:
        report.update(metadata)
    stem = 'submission-demo' if mode == 'live' else 'offline-demo'
    (directory/(stem+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines = [f'# {mode.capitalize()} submission demo log', '',
             f'Recorded: {report["recorded_at"]}', '',
             'Actual application output using synthetic customers and temporary SQLite databases.', '',
             f'Checks: {report["passed"]}/{report["total"]}.', '']
    for number, record in enumerate(records,1):
        lines += [f'## {number}. {record["label"]}', '', f'Session: `{record["session"]}`', '',
                  'Result: '+('PASS' if not record['issues'] else 'FAIL'), '']
        if 'question' in record:
            lines += ['Customer:', '', record['question'], '', 'Assistant (verbatim):', '', record['answer'], '',
                      'Executed nodes: `'+' → '.join(record['nodes'])+'`', '']
        if 'observed' in record:
            lines += ['Observed saved data:', '', '```json', json.dumps(record['observed'],ensure_ascii=False,indent=2), '```', '']
        if record['issues']:
            lines += ['Issues: '+ '; '.join(record['issues']), '']
        if record.get('checker_review'):
            lines += ['Checker review: '+record['checker_review'], '']
    (directory/(stem+'.md')).write_text('\n'.join(lines),encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',help='Billable OpenAI run with synthetic messages and brochure pages')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'work'/'submission-demo',help='Destination for sanitized demo logs')
    parser.add_argument('--history-probe',nargs=2,metavar=('ISOLATED_DIRECTORY','SESSION'),help=argparse.SUPPRESS)
    parser.add_argument('--recheck-log',type=Path,help='Locally accept the documented entry-age paraphrase in a recorded log; no API calls')
    args = parser.parse_args()
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if args.history_probe:
        print(json.dumps(history_probe(Path(args.history_probe[0]),args.history_probe[1]),ensure_ascii=False))
        return
    if args.recheck_log:
        original = json.loads(args.recheck_log.read_text(encoding='utf-8'))
        records = original['records']
        before = json.dumps([r.get('answer') for r in records],ensure_ascii=False)
        for record in records:
            if record['label'] != 'Pension duration uses entry age':
                continue
            answer = record['answer'].casefold()
            if record['issues'] == ['Missing expected answer fragment: entry age'] and 'no' in answer and '05_scb' in answer and any(phrase in answer for phrase in ('entry age','age at entry')):
                record['original_checker_issues'] = list(record['issues'])
                record['checker_review'] = 'Accepted the valid phrase "age at entry" after source review. Actual answer unchanged; original strict-checker result is preserved.'
                record['issues'] = []
        assert before == json.dumps([r.get('answer') for r in records],ensure_ascii=False)
        report = write_log(args.recheck_log.parent,records,original['mode'],original.get('chat_model'),
                           {'recorded_at':original['recorded_at'],'checker_reviewed_at':datetime.now(ZoneInfo('Asia/Bangkok')).isoformat(),
                            'checker_revision_only':'One valid entry-age paraphrase accepted. No answers or stored data were changed.'})
        print(f"{report['passed']}/{report['total']} recorded checks accepted; no API calls.")
        if report['passed'] != report['total']:
            raise SystemExit(1)
        return
    from langchain_core.messages import HumanMessage
    from insurex.config import Settings
    from insurex.web_service import ChatService
    from insurex.lead_storage import read_leads
    from insurex.sessions import list_sessions

    settings = Settings.load()
    records = []
    mode = 'live' if args.live else 'offline'
    (ROOT/'work').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='submission-demo-',dir=ROOT/'work') as temporary:
        isolated = Path(temporary)
        settings = replace(settings,session_db=isolated/'sessions.sqlite',lead_db=isolated/'leads.sqlite')
        assistant = ChatService(settings,offline=not args.live)

        def observation(label,session,observed,issues):
            records.append({'label':label,'session':session,'observed':observed,'issues':issues})
            write_log(args.output_dir,records,mode,settings.chat_model)
            print(f'{label}: '+('PASS' if not issues else 'FAIL '+ '; '.join(issues)),flush=True)

        def send(label,session,question,contains=(),absent=(),contains_any=(),expected_mode=None,active=None,saved=None):
            nodes = []
            with assistant.graph() as graph:
                for update in graph.stream({'messages':[HumanMessage(content=question)]},assistant.config(session),stream_mode='updates'):
                    nodes.extend(update.keys())
                state = graph.get_state(assistant.config(session)).values
            answer = str(state['messages'][-1].content)
            issues = []
            if state.get('error'):
                issues.append(state['error'])
            for fragment in contains:
                if fragment.casefold() not in answer.casefold():
                    issues.append('Missing expected answer fragment: '+fragment)
            for fragment in absent:
                if fragment.casefold() in answer.casefold():
                    issues.append('Unexpected answer fragment: '+fragment)
            for alternatives in contains_any:
                if not any(fragment.casefold() in answer.casefold() for fragment in alternatives):
                    issues.append('Missing all valid answer alternatives: '+', '.join(alternatives))
            for key,expected in [('mode',expected_mode),('lead_active',active),('lead_saved',saved)]:
                if expected is not None and state.get(key,False) != expected:
                    issues.append(f'{key}: expected {expected}, got {state.get(key)}')
            if label == 'Detailed critical illness comparison':
                from insurex.answer_checks import unsupported_ci50_count
                if unsupported_ci50_count(answer):
                    issues.append('Unsupported CI 50 illness-count claim.')
            records.append({'label':label,'session':session,'question':question,'answer':answer,'nodes':nodes,
                            'mode':state.get('mode'),'issues':issues})
            write_log(args.output_dir,records,mode,settings.chat_model)
            print(f'{label}: '+('PASS' if not issues else 'FAIL '+ '; '.join(issues)),flush=True)
            return state

        send('All five brochures','demo-catalog','What products are available?',
             contains=('Cheeva','Bamnan','Maojai','Aomsook','CI Plus'),expected_mode='catalog_list')
        send('Shortest fixed premium period','demo-catalog','Which product has the shortest premium-payment period?',
             contains=('90/5: 5 years',),expected_mode='payment_rank')
        if args.live:
            send('Customer A life goal','demo-a','I am a frugal customer, age 22. Annual insurance budget 20000 THB. I want my family to receive money if I die. No existing insurance.',contains=('Cheeva',),expected_mode='recommendation')
            send('Customer B medical goal','demo-b','I am age 45. Annual insurance budget 60000 THB. I want help paying hospital bills. No existing insurance.',contains=('Maojai',),expected_mode='recommendation')
            send('Customer A recall stays separate','demo-a','What age, annual budget and goal have I told you?',contains=('22','20000'),absent=('45','60000'),expected_mode='profile_recall')
            send('Explicit interest activates tooling','demo-a','I am interested in Khum Cheeva.',active=True,saved=False)
            send('Collect only supplied fields','demo-a','My name is Demo Alex. I am a student. My income is 20,000 THB per month. My insurance budget is 20000 THB per year.',active=True,saved=False)
            checkpoint = assistant.history('demo-a')
            probe = subprocess.run([sys.executable,str(Path(__file__).resolve()),'--history-probe',str(isolated),'demo-a'],
                                   capture_output=True,text=True,encoding='utf-8',timeout=45)
            if probe.returncode:
                observation('Independent process restores draft','demo-a',{'process_exit':probe.returncode},['Checkpoint probe did not complete.'])
            else:
                restored = json.loads(probe.stdout)
                expected = checkpoint['lead_draft']
                issues = [] if restored['lead_draft'] == expected and restored['lead_active'] else ['Draft or active collection changed after restart.']
                observation('Independent process restores draft','demo-a',restored,issues)
            assistant = ChatService(settings,offline=False)
            send('Factual interruption preserves draft','demo-a','For Khum Cheeva, how many years do I pay the base-policy premiums?',contains=('10','02_SCB'),active=True,saved=False)
            send('Invalid phone does not save','demo-a','My contact number is 123.',contains=('8–15',),active=True,saved=False)
            rows = read_leads(settings.lead_db,'demo-a')
            observation('Incomplete lead is absent from SQLite','demo-a',rows,[] if not rows else ['Incomplete lead was saved.'])
            send('Complete lead is saved','demo-a','My contact number is 0800000000.',contains=('saved',),active=False,saved=True)
            rows = read_leads(settings.lead_db,'demo-a')
            expected = {'product_id':'cheeva','name':'Demo Alex','occupation':'student','income':'20,000 THB per month','contact_number':'0800000000'}
            issues = []
            if len(rows) != 1 or any(rows[0].get(key) != value for key,value in expected.items()):
                issues.append('Stored structured fields do not match supplied customer values.')
            observation('Structured SQLite record matches customer','demo-a',rows,issues)
            send('Customer B remains independent','demo-b','What age, annual budget and protection goal have I told you?',contains=('45','60000'),absent=('22','Demo Alex','0800000000'),expected_mode='profile_recall')
            send('Thai product interest','demo-thai','สนใจคุ้มออมสุขค่ะ',active=True,saved=False)
            send('Thai structured lead','demo-thai','ชื่อ เดโมบี อาชีพ ครู รายได้ 30000 บาทต่อเดือน เบอร์ติดต่อ 0811111111',active=False,saved=True)
            thai_rows = read_leads(settings.lead_db,'demo-thai')
            observation('Thai record is separate','demo-thai',thai_rows,[] if len(thai_rows)==1 and thai_rows[0]['product_id']=='aomsook' and thai_rows[0]['contact_number']=='0811111111' else ['Thai lead save mismatch.'])
            send('Start incomplete lead','demo-cancel','I am interested in Khum Talodcheep CI Plus.',active=True,saved=False)
            send('Cancel without saving','demo-cancel','/cancel-lead',active=False,saved=False)
            cancelled = read_leads(settings.lead_db,'demo-cancel')
            observation('Cancelled lead is absent from SQLite','demo-cancel',cancelled,[] if not cancelled else ['Cancelled lead was saved.'])
            send('Detailed critical illness comparison','demo-rag','What is the difference between the critical illness protection in Khum Cheeva and Khum Talodcheep CI Plus?',contains=('02_SCB','11_SCB','25%','100%','CI 50'))
            send('Health rider dependency','demo-rag','Does Khum Raksa Maojai Extra need an eligible base life policy?',contains=('07_SCB',))
            send('Savings coverage and payment separation','demo-rag','For Khum Aomsook 25/15, what are the coverage and premium-payment periods?',contains=('25','15','09_SCB'))
            send('Pension duration uses entry age','demo-rag','For Khum Bamnan 85/55, does everyone pay premiums for exactly 10 years?',contains=('No','05_SCB'),contains_any=(('entry age','age at entry'),))
            send('Missing product evidence','demo-unknown','What does the nonexistent product Demo Unicorn 123 cover?',absent=('Demo Unicorn provides','guaranteed'))
        else:
            send('Offline second session','demo-b','How many years do I pay premiums for Khum Cheeva?',contains=('10','02_SCB'))
            restored = history_probe(isolated,'demo-catalog')
            observation('Offline history restored','demo-catalog',restored,[] if len(restored['history'])==4 else ['History restore mismatch.'])
        sessions = list_sessions(settings.session_db)
        observation('Saved session IDs are separate','all',sessions,[] if 'demo-catalog' in sessions and 'demo-b' in sessions else ['Expected session IDs were not saved.'])
    report = write_log(args.output_dir,records,mode,settings.chat_model)
    print(f"{report['passed']}/{report['total']} checks passed. Logs: {args.output_dir}")
    if report['passed'] != report['total']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
