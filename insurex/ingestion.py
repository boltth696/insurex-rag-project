import hashlib
import json
import subprocess
import sys
from pathlib import Path
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Windows Thai legacy PUA glyphs, U+F700..F71A, in the supplied brochures.
# Reference: https://linux.thai.net/~thep/th-otf/shaping.html
_THAI_PUA = dict(enumerate([
    0x0E10, 0x0E34, 0x0E35, 0x0E36, 0x0E37,
    0x0E48, 0x0E49, 0x0E4A, 0x0E4B, 0x0E4C,
    0x0E48, 0x0E49, 0x0E4A, 0x0E4B, 0x0E4C,
    0x0E0D, 0x0E31, 0x0E4D, 0x0E47,
    0x0E48, 0x0E49, 0x0E4A, 0x0E4B, 0x0E4C,
    0x0E38, 0x0E39, 0x0E3A,
], start=0xF700))


def normalize_thai(text):
    # Normalize only the known font variants, leaving other text untouched.
    return text.translate(_THAI_PUA)


def load_pages(pdf_dir: Path):
    paths = sorted(pdf_dir.glob("*.pdf"))
    if not paths:
        raise ValueError(f"No PDFs found in {pdf_dir}")
    documents, report = [], []
    for path in paths:
        # PDF parsing is isolated: a native interpreter fault must not kill
        # ingestion, inspection or the test runner. Worker failure gets one
        # retry: the Windows Python launcher can collapse a native exit to 1.
        worker = Path(__file__).with_name("pdf_worker.py")
        for attempt in range(2):
            try:
                result = subprocess.run([sys.executable, "-I", str(worker), str(path.resolve())], capture_output=True, timeout=60)
            except subprocess.TimeoutExpired as exc:
                raise ValueError(f"PDF extraction timed out: {path.name}") from exc
            if result.returncode == 0:
                raw_pages = json.loads(result.stdout.decode("utf-8"))
                break
            if attempt == 1:
                lines = (result.stderr or b'').decode('utf-8',errors='replace').strip().splitlines()
                detail = lines[-1][:200] if lines else 'No worker diagnostic available.'
                raise ValueError(f"PDF extraction failed for {path.name} (process exit {result.returncode}). The source was not indexed. {detail}")
        page_report = []
        for number, raw in enumerate(raw_pages, start=1):
            raw = raw.strip()
            text = normalize_thai(raw)
            repaired = sum(ord(c) in _THAI_PUA for c in raw)
            thai = sum("\u0e00" <= c <= "\u0e7f" for c in text)
            page_report.append({"page": number, "characters": len(text), "thai_characters": thai, "legacy_thai_characters_normalized": repaired})
            if text:
                documents.append(Document(page_content=text, metadata={"source": path.name, "page": number}))
        report.append({"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "pages": page_report})
    return documents, report


def split_pages(pages, settings):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", " ", "\u200b", ""],
    )
    return splitter.split_documents(pages)


def inspect_pdfs(settings):
    _, report = load_pages(settings.pdf_dir)
    settings.index_dir.parent.mkdir(parents=True, exist_ok=True)
    target = settings.index_dir.parent / "extraction-report.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report, target
