"""Reviewed, source-bound product facts and local catalog answers."""
import hashlib
import json
import re
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field, model_validator
from .comparison import quote_key, recommendation_intent
from .config import ROOT


class Variant(BaseModel):
    plan: str
    payment_years: int | None = Field(default=None, gt=0)
    payment_until_age: int | None = Field(default=None, gt=0)


class Evidence(BaseModel):
    page: int = Field(gt=0)
    fields: list[str]
    quote: str


class Product(BaseModel):
    id: str
    name_th: str
    name_en: str
    aliases: list[str]
    category_en: str
    category_th: str
    coverage_kind: Literal["years", "until_age", "conditional_until_age"]
    coverage_value: int = Field(gt=0)
    payment_kind: Literal["fixed", "until_age", "not_fixed"]
    variants: list[Variant]
    source_file: str
    source_sha256: str
    evidence: list[Evidence]
    review_note: str

    @model_validator(mode="after")
    def validate_fields(self):
        if Path(self.source_file).name != self.source_file:
            raise ValueError("Catalog source must be a filename.")
        if not self.variants or not self.evidence:
            raise ValueError("Catalog variants and evidence are required.")
        if self.payment_kind == "fixed" and any(v.payment_years is None or v.payment_until_age is not None for v in self.variants):
            raise ValueError("Fixed payment variants require payment_years only.")
        if self.payment_kind == "until_age" and any(v.payment_until_age is None or v.payment_years is not None for v in self.variants):
            raise ValueError("Age-based payment variants require payment_until_age only.")
        if self.payment_kind == "not_fixed" and any(v.payment_years is not None or v.payment_until_age is not None for v in self.variants):
            raise ValueError("Unspecified fixed periods cannot enter numerical comparisons.")
        if not {"name", "category", "coverage", "payment"} <= {f for e in self.evidence for f in e.fields}:
            raise ValueError("All catalog facts require source evidence.")
        return self


class Catalog(BaseModel):
    schema_version: Literal[1]
    products: list[Product]


def load_catalog(path=ROOT / "data/product_catalog.json", pdf_dir=ROOT / "data/pdfs"):
    catalog = Catalog.model_validate_json(Path(path).read_text(encoding="utf-8"))
    actual = {p.name for p in Path(pdf_dir).glob("*.pdf")}
    sources = [p.source_file for p in catalog.products]
    if set(sources) != actual or len(sources) != len(actual):
        raise ValueError("Catalog must cover each local PDF exactly once. Review it after adding/removing PDFs.")
    if len({p.id for p in catalog.products}) != len(catalog.products):
        raise ValueError("Catalog product IDs must be unique.")
    for p in catalog.products:
        if hashlib.sha256((Path(pdf_dir) / p.source_file).read_bytes()).hexdigest() != p.source_sha256:
            raise ValueError(f"PDF changed: {p.source_file}. Review the catalog before answering.")
    return catalog


def verify_catalog_evidence(catalog, pages):
    """Local audit: quote existence and numeric support, not automated semantic review."""
    lookup = {(d.metadata["source"], d.metadata["page"]): d.page_content for d in pages}
    for p in catalog.products:
        for e in p.evidence:
            text = lookup.get((p.source_file, e.page), "")
            if not e.quote.strip() or quote_key(e.quote) not in quote_key(text):
                raise ValueError(f"Catalog evidence changed: {p.source_file}, page {e.page}.")
        numeric = " ".join(e.quote for e in p.evidence if {"coverage", "payment"} & set(e.fields))
        numbers = [p.coverage_value] + [v.payment_years or v.payment_until_age for v in p.variants if v.payment_years or v.payment_until_age]
        if any(not re.search(rf"(?<![0-9]){n}(?![0-9])", numeric) for n in numbers):
            raise ValueError(f"Missing numeric support for {p.source_file}.")
    from .benefits import benefit_notes
    for page in pages:
        benefit_notes(catalog, page)
    return True


def matching_products(catalog, question):
    q = question.lower().replace("-", "/")
    named = [p for p in catalog.products if any(a.lower() in q for a in [p.name_th, p.name_en, *p.aliases] if not re.fullmatch(r"\d+/\d+", a))]
    if named:
        return named
    # A code such as 90/10 can belong to several products; do not silently pick one.
    codes = set(re.findall(r"\b\d+/\d+\b", q))
    return [p for p in catalog.products if codes & {v.plan for v in p.variants}]


def catalog_intent(question, catalog):
    q = question.lower()
    if recommendation_intent(question):
        return None
    details = any(t in q for t in ("exclusion", "waiting", "maternity", "dental", "claim", "premium amount", "how much", "ข้อยกเว้น", "ระยะรอ", "ค่าคลอด", "ราคา", "เคลม"))
    details = details or bool(re.search(r"\b(cover|covers|covered|benefits?|cancer|pregnancy|transplant|illness|protection|cheaper|cheapest|costs?|prices?|expensive|budget)\b", q)) or any(t in q for t in ("โรคร้ายแรง", "ผลประโยชน์", "ถูกกว่า", "ถูกที่สุด", "ราคา", "งบ"))
    details = details or bool(re.search(r"\briders?\b|\bci\s*50\b|eligib|entry.age|sums?[\s-]+(?:insured|assured)|underwrit|automatically|\balways\b|\bexample\b|\bplan\s*\d|annual.payment premium|สัญญาเพิ่มเติม|รับประกัน|ทุนประกัน|ตัวอย่าง", q))
    details = details or bool(re.search(r'compare|versus|\bvs\b|เปรียบเทียบ',q) and re.search(r'premium|payment|เบี้ย',q))
    # A personal spending limit or customer profile is not a catalog request.
    personal_context = bool(re.search(r"\d|\b(i|my|me|we|our|customers?|pay|spend|monthly|yearly|need|want|children|family)\b", q)) or any(t in q for t in ("ฉัน", "อายุ", "รายได้", "เดือนละ"))
    listing = (bool(re.search(r"\b(products?|policies|plans?|options?)\b", q)) and any(t in q for t in ("what", "which", "list", "available", "choose", "offer", "there", "options"))) or any(t in q for t in ("มีประกันอะไร", "มีแผนอะไร", "มีผลิตภัณฑ์อะไร", "เลือกอะไรได้บ้าง", "รายชื่อ", "มีอะไรให้เลือก"))
    details = details or bool(re.search(r'\b(everyone|everybody|anyone|all ages)\b|ทุกคน|ทุกอายุ',q))
    if listing and not details and not personal_context:
        return "catalog_list"
    if not details and any(t in q for t in ("compare", "เปรียบเทียบ")) and any(t in q for t in ("all", "ทุก", "ทั้งหมด")):
        return "catalog_list"
    duration = any(t in q for t in ("years", "how long", "until what age", "coverage period", "payment period", "pay premiums", "pay the premium", "กี่ปี", "ถึงอายุ", "ระยะเวลาชำระ", "ระยะเวลาคุ้มครอง"))
    if duration and not details and matching_products(catalog, question):
        return "catalog_fact"
    return None


def product_text(p, language):
    thai = language == "Thai"
    name = p.name_th + " (" + ", ".join(v.plan for v in p.variants) + ")"
    if not thai:
        name = p.name_en + " / " + name
    category = p.category_th if thai else p.category_en
    if p.coverage_kind == "years":
        coverage = f"คุ้มครอง {p.coverage_value} ปี" if thai else f"Coverage: {p.coverage_value} years"
    else:
        coverage = f"คุ้มครองถึงอายุ {p.coverage_value} ปี" if thai else f"Coverage: until age {p.coverage_value}"
        if p.coverage_kind == "conditional_until_age":
            coverage += " หรือไม่เกินระยะเวลาคุ้มครองของกรมธรรม์ประกันชีวิต ตามเงื่อนไข" if thai else ", or the base life policy's coverage term if shorter, subject to conditions"
    if p.payment_kind == "fixed":
        values = ", ".join(str(v.payment_years) for v in p.variants)
        payment = f"ชำระเบี้ย {values} ปี ตามตัวเลือกแผน" if thai else f"Premium payments: {values} years, depending on the variant"
    elif p.payment_kind == "until_age":
        options = "; ".join(f"{v.plan}: " + (f"ถึงอายุ {v.payment_until_age} ปี" if thai else f"until age {v.payment_until_age}") for v in p.variants)
        payment = ("ชำระเบี้ย " if thai else "Premium payments: ") + options
    else:
        payment = "เอกสารไม่ได้ระบุระยะเวลาชำระเบี้ยแบบกำหนดจำนวนปี" if thai else "The brochure does not specify a fixed number of premium-payment years"
    return f"{name}: {category}. {coverage}. {payment}."


def source_lines(products, language):
    lines = ["\nแหล่งข้อมูล:" if language == "Thai" else "\nSources:"]
    for i, p in enumerate(products, 1):
        pages = ", ".join(str(x) for x in sorted({e.page for e in p.evidence}))
        lines.append(f"[{i}] {p.source_file}, pages {pages}")
    return lines


def render_catalog(catalog, language, question, mode):
    products = catalog.products
    if mode == "catalog_fact":
        matches = matching_products(catalog, question)
        if len(matches) != 1:
            names = ", ".join(p.name_en for p in matches)
            return ("กรุณาระบุชื่อผลิตภัณฑ์ เพราะรหัสแผนตรงกับหลายผลิตภัณฑ์: " if language == "Thai" else "Please specify the product name; that plan code matches several products: ") + names
        products = matches
    heading = (f"เอกสารที่ให้มามีผลิตภัณฑ์ {len(products)} กลุ่ม:" if language == "Thai" else f"The supplied brochures describe these {len(products)} product families:") if mode == "catalog_list" else ("ข้อมูลแผนประกัน:" if language == "Thai" else "Verified plan terms:")
    lines = [heading]
    lines += [f"{i}. {product_text(p, language)} [{i}]" for i, p in enumerate(products, 1)]
    lines.extend(source_lines(products, language))
    return "\n\n".join(lines)


def render_payment_ranking(catalog, language, question):
    longest = any(t in question.lower() for t in ("longest", "most years", "maximum", "ยาวที่สุด", "มากที่สุด"))
    named = matching_products(catalog, question)
    broad = bool(re.search(r"\b(all|every)\b", question, re.I)) or any(t in question for t in ("ทั้งหมด", "ทุก"))
    products = named if named and not broad else catalog.products
    options = [(v.payment_years, p, v) for p in products if p.payment_kind == "fixed" for v in p.variants]
    if not options:
        prefix = "แผนที่ระบุไม่มีระยะเวลาชำระเบี้ยแบบกำหนดจำนวนปีสำหรับจัดอันดับ" if language == "Thai" else "The specified product has no fixed payment-year options to rank. Pension duration requires your entry age."
        return prefix + "\n\n" + render_catalog(catalog, language, question, "catalog_fact" if len(named) == 1 else "catalog_list")
    best = (max if longest else min)(n for n, _, _ in options)
    winners = [(p, v) for n, p, v in options if n == best]
    names = ", ".join(p.name_th + " " + v.plan for p, v in winners)
    if language == "Thai":
        text = f"ตัวเลือกที่มีระยะเวลาชำระเบี้ยแบบกำหนดจำนวนปี{'ยาวที่สุด' if longest else 'สั้นที่สุด'}คือ {names}: {best} ปี"
    else:
        text = f"The {'longest' if longest else 'shortest'} fixed premium-payment option is {names}: {best} years."
    text += "\n\n" + render_catalog(catalog, language, question, "catalog_list")
    text += "\n\n" + ("การจัดอันดับนี้เปรียบเทียบเฉพาะจำนวนปีที่กำหนดไว้ แผนบำนาญต้องทราบอายุเริ่มทำประกันก่อนจึงจะคำนวณระยะเวลาชำระเบี้ยเฉพาะบุคคลได้ สัญญาเพิ่มเติมสุขภาพไม่ได้ระบุระยะเวลาชำระเบี้ยแบบกำหนดจำนวนปี" if language == "Thai" else "This ranks fixed payment-year options only. Pension payment durations depend on your entry age; the health rider has no stated fixed payment-year period. These are not ranked as fixed-year plans.")
    return text
