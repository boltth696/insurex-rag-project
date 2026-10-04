"""Local data inspection must work without model/retrieval imports."""
import subprocess
import sys
from pathlib import Path
import pytest


@pytest.mark.parametrize("command,expected", [("sessions","Saved sessions: 0"),("leads","[]")])
def test_local_cli_does_not_load_api_or_native_retrieval_libraries(tmp_path, command, expected):
    root = Path(__file__).resolve().parents[1]
    script = '''
import importlib.abc, sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1])
class Blocked(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'langchain_openai','langchain_core','langgraph','faiss','numpy','pydantic'}:
            raise ImportError('Unnecessary dependency: ' + fullname)
sys.meta_path.insert(0, Blocked())
from insurex import cli
storage = Path(sys.argv[2])
cli.Settings.load = lambda: SimpleNamespace(session_db=storage/'sessions.sqlite',lead_db=storage/'leads.sqlite')
sys.argv = ['insurex.cli', sys.argv[3]]
cli.main()
'''
    result = subprocess.run([sys.executable,"-I","-c",script,str(root),str(tmp_path),command],capture_output=True,text=True,timeout=15)
    assert result.returncode == 0, result.stderr
    assert expected in result.stdout
    assert not list(tmp_path.iterdir())
