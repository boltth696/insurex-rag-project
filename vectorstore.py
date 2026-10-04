import json
import hashlib
from pathlib import Path
import uuid
import faiss
from langchain_community.vectorstores import FAISS
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_core.documents import Document
from .ingestion import load_pages, split_pages


def build_index(settings):
    from langchain_openai import OpenAIEmbeddings
    print("Reading PDF pages...", flush=True)
    pages, report = load_pages(settings.pdf_dir)
    empty = [(item["file"], page["page"]) for item in report for page in item["pages"] if page["characters"] < 30]
    if empty:
        raise ValueError(f"Pages have too little extracted text; inspect/OCR these before indexing: {empty}")
    chunks = split_pages(pages, settings)
    print(f"Creating embeddings for {len(chunks)} chunks with {settings.embedding_model}...", flush=True)
    embeddings = OpenAIEmbeddings(model=settings.embedding_model, request_timeout=60, max_retries=2)
    store = FAISS.from_documents(chunks, embeddings, normalize_L2=True)
    print("Saving FAISS index...", flush=True)
    save_index(store, settings.index_dir, {"embedding_model": settings.embedding_model, "files": report, "chunks": len(chunks)})
    return len(pages), len(chunks)


def save_index(store, folder, manifest):
    # Persist documents as JSON instead of FAISS.save_local's pickle file.
    folder.mkdir(parents=True, exist_ok=True)
    generation = uuid.uuid4().hex
    index_name, docs_name = f"{generation}.faiss", f"{generation}.json"
    faiss.write_index(store.index, str(folder / index_name))
    rows = []
    for position, doc_id in sorted(store.index_to_docstore_id.items()):
        doc = store.docstore.search(doc_id)
        rows.append({"position": position, "id": doc_id, "text": doc.page_content, "metadata": doc.metadata})
    (folder / docs_name).write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    complete = {**manifest, "index_file": index_name, "documents_file": docs_name}
    temporary = folder / "manifest.tmp"
    temporary.write_text(json.dumps(complete, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(folder / "manifest.json")


def load_index(settings, embeddings=None):
    folder = settings.index_dir
    if not (folder / "manifest.json").exists():
        raise ValueError("FAISS index is missing. Run: python -m insurex.cli ingest")
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if manifest["embedding_model"] != settings.embedding_model:
        raise ValueError("EMBEDDING_MODEL changed. Rebuild the index before chatting.")
    # A reviewed catalog update cannot make an old FAISS index current.
    if 'files' in manifest:
        current = {p.name: p for p in settings.pdf_dir.glob('*.pdf')}
        indexed = {item['file']: item['sha256'] for item in manifest['files']}
        if set(current) != set(indexed) or any(hashlib.sha256(path.read_bytes()).hexdigest() != indexed[name] for name, path in current.items()):
            raise ValueError('Source PDFs changed since indexing. Review the catalog and rebuild the FAISS index before chatting.')
    for key in ("index_file", "documents_file"):
        if Path(manifest[key]).name != manifest[key]:
            raise ValueError("Invalid index manifest filename.")
    rows = json.loads((folder / manifest["documents_file"]).read_text(encoding="utf-8"))
    index = faiss.read_index(str(folder / manifest["index_file"]))
    if index.ntotal != len(rows):
        raise ValueError("Index and document count disagree. Rebuild the index.")
    docs = {r["id"]: Document(page_content=r["text"], metadata=r["metadata"]) for r in rows}
    mapping = {r["position"]: r["id"] for r in rows}
    if embeddings is None:
        from langchain_openai import OpenAIEmbeddings
        embeddings = OpenAIEmbeddings(model=settings.embedding_model, request_timeout=60, max_retries=2)
    return FAISS(embeddings, index, InMemoryDocstore(docs), mapping, normalize_L2=True)
