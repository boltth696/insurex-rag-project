"""Local PDF text extraction in a disposable process; no API calls."""
import json
import sys
import faulthandler
faulthandler.enable()
from pypdf import PdfReader


if __name__ == "__main__":
    reader = PdfReader(sys.argv[1])
    payload = [page.extract_text() or "" for page in reader.pages]
    sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
