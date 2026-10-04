"""Attach reviewed table interpretations only to their matching source page."""
import json
from .config import ROOT
from .comparison import quote_key


def benefit_notes(catalog, document):
    products = {p.id: p for p in catalog.products}
    notes = json.loads((ROOT / "data/benefit_notes.json").read_text(encoding="utf-8"))["notes"]
    result = []
    for note in notes:
        product = products.get(note["product_id"])
        if product is None or product.source_file != document.metadata["source"] or note["page"] != document.metadata["page"]:
            continue
        if quote_key(note["quote"]) not in quote_key(document.page_content):
            raise ValueError("Reviewed benefit note is missing its source-page evidence.")
        result.append(note["text"])
    return "\n".join(result)
