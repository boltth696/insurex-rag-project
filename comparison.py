"""Evidence extraction and deterministic premium-payment comparisons."""
import re
import unicodedata
from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.documents import Document


def quote_key(text):
    # Thai SARA AM can be encoded as one character or decomposed glyphs in PDFs.
    # Normalize equivalent Unicode and whitespace; preserve digits and wording.
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


def page_evidence(chunks):
    """Rejoin ordered overlapping index chunks within each source page."""
    grouped = {}
    for doc in chunks:
        key = (doc.metadata["source"], doc.metadata["page"])
        if key not in grouped:
            grouped[key] = doc.page_content
            continue
        previous = grouped[key]
        overlap = 0
        for size in range(min(len(previous), len(doc.page_content)), 19, -1):
            if previous.endswith(doc.page_content[:size]):
                overlap = size
                break
        grouped[key] = previous + (doc.page_content[overlap:] if overlap else "\n" + doc.page_content)
    return [Document(page_content=text, metadata={"source": source, "page": page})
            for (source, page), text in grouped.items()]


class PaymentTerm(BaseModel):
    source_file: str = Field(description="Exact PDF filename from evidence; one row per PDF.")
    product: str = Field(description="Product name and applicable variants, using source wording.")
    kind: Literal["fixed", "age_based", "renewable", "unspecified"] = Field(description="Fixed number of payment years, payments until a specified age, annual renewable rider, or unavailable. Never classify a worked example as the universal payment period.")
    years: list[int] = Field(description="All explicitly stated fixed payment-year options; empty for other kinds. Do not use coverage years, entry ages, benefit periods, or an example customer's duration.")
    citation_id: int = Field(description="Passage ID supporting these terms.")
    evidence_quote: str = Field(description="Exact contiguous quotation showing the claimed payment terms. Preserve characters and punctuation. For unspecified, use an empty string: absence of a fixed payment period cannot be quoted. Never invent a statement that the PDF does not contain.")


class PaymentComparison(BaseModel):
    terms: list[PaymentTerm] = Field(description="Exactly one row for EACH PDF filename in the evidence, even when payment years are unavailable.")


def response_language(question):
    # English questions can contain Thai product names.
    if re.search(r"\b(answer|respond|reply)\b.*\benglish\b", question, re.I):
        return "English"
    if re.search(r"(ตอบ|ภาษา).*ไทย", question):
        return "Thai"
    latin = len(re.findall(r"[A-Za-z]", question))
    thai = len(re.findall(r"[\u0e00-\u0e7f]", question))
    return "English" if latin > thai or not thai else "Thai"


def comparison_intent(question):
    q = question.lower()
    # Match only stand-alone greetings, so "hello, compare premiums" still
    # reaches the insurance workflow. Previous turns must not reinterpret this.
    if re.fullmatch(r"\s*(?:hello|hi|hey|good morning|good afternoon|good evening|สวัสดี(?:ครับ|ค่ะ|คะ)?)[\s!.?]*", q):
        return "greeting"
    if recommendation_intent(question):
        return "recommendation"
    rank = any(t in q for t in ("shortest", "fewest", "least", "minimum", "longest", "most years", "maximum", "สั้นที่สุด", "น้อยที่สุด", "น้อยสุด", "สั้นสุด", "ยาวที่สุด", "มากที่สุด"))
    payment = any(t in q for t in ("prem", "pay", "เบี้ย", "ชำระ", "จ่าย"))
    duration = any(t in q for t in ("year", "duration", "period", "shortest", "longest", "ปี", "ระยะ", "สั้น", "ยาว"))
    amount_question = bool(re.search(r"(?:minimum|maximum|least|lowest|highest)\s+(?:sums? (?:insured|assured)|coverage amount|benefit amount|death benefit)|(?:ทุนประกัน|จำนวนเงินเอาประกันภัย).{0,15}(?:ขั้นต่ำ|สูงสุด)", q))
    if rank and payment and duration and not amount_question:
        return "payment_rank"
    if re.search(r"\bwhich products?\b", q) or any(t in q for t in ("all policies", "all of the policies", "all plans", "all products", "every policy", "compare", "comparison", "which policy", "which plan", "which is", "เปรียบเทียบ", "ทุกแผน", "ทุกกรมธรรม์", "ทั้งหมด", "แผนไหน", "แบบไหน")):
        return "all_products"
    return "single"


def recommendation_intent(question):
    """Suitability questions must not be mistaken for a request to list products."""
    q = question.lower()
    return bool(re.search(r"\b(recommend\w*|suggest\w*|suits?|suitable|suitability|affordable|affordability|best|better)\b", q)) or any(t in q for t in ("แนะนำ", "เหมาะ", "งบน้อย", "รายได้น้อย", "คุ้มที่สุด"))


def validate_terms(result, evidence):
    expected = {d.metadata["source"] for d in evidence}
    actual = [t.source_file for t in result.terms]
    if set(actual) != expected or len(actual) != len(expected):
        raise ValueError("Comparison must cover every PDF exactly once.")
    for term in result.terms:
        if not 1 <= term.citation_id <= len(evidence):
            raise ValueError("Invalid comparison citation.")
        doc = evidence[term.citation_id - 1]
        if doc.metadata["source"] != term.source_file:
            raise ValueError("Comparison citation points to the wrong PDF.")
        if term.kind != "fixed" and term.years:
            raise ValueError("Non-fixed payment terms must not enter the numerical ranking.")
        if term.kind == "unspecified":
            # This row expresses uncertainty, not a fact about a payment duration.
            term.evidence_quote = ""
            continue
        if not term.evidence_quote.strip():
            if term.kind != "fixed":
                term.kind = "unspecified"
                continue
            raise ValueError(f"Empty evidence quote for {term.source_file}.")
        if quote_key(term.evidence_quote) not in quote_key(doc.page_content):
            # Correct a misplaced page reference only when the exact quote is
            # present elsewhere in the SAME PDF. Never accept paraphrases.
            matches = [i for i, d in enumerate(evidence, 1)
                       if d.metadata["source"] == term.source_file
                       and quote_key(term.evidence_quote) in quote_key(d.page_content)]
            if not matches:
                if term.kind != "fixed":
                    # Discard the unsupported age/renewal assertion rather than
                    # pretend it is a fact or block verified fixed-year products.
                    term.kind = "unspecified"
                    term.evidence_quote = ""
                    continue
                raise ValueError(f"Evidence quote for {term.source_file} is not present in that PDF. Copy a shorter exact contiguous quote, without paraphrasing or joining distant lines.")
            term.citation_id = matches[0]
        if term.kind == "fixed":
            if not term.years or any(y <= 0 for y in term.years):
                raise ValueError("Fixed payment years must be positive.")
            for year in term.years:
                if not re.search(rf"(?<![0-9]){year}(?![0-9])", term.evidence_quote):
                    raise ValueError("Payment years are not supported by the quote.")
            if not re.search(r"ปี|years?", term.evidence_quote, re.I):
                raise ValueError("A plan-code suffix is not evidence of a payment duration.")
        elif term.years:
            raise ValueError("Non-fixed payment terms must not enter the numerical ranking.")
    return result.terms


def render_comparison(terms, evidence, language, question):
    fixed = [(y, t) for t in terms if t.kind == "fixed" for y in t.years]
    thai = language == "Thai"
    longest = any(t in question.lower() for t in ("longest", "most years", "maximum", "ยาวที่สุด", "มากที่สุด"))
    lines = []
    if fixed:
        best = (max if longest else min)(y for y, _ in fixed)
        winners = list(dict.fromkeys(t.product for y, t in fixed if y == best))
        names = ", ".join(winners)
        if thai:
            adjective = "ยาวที่สุด" if longest else "สั้นที่สุด"
            lines.append(f"ตัวเลือกที่มีระยะเวลาชำระเบี้ยแบบกำหนดจำนวนปี{adjective}คือ {names}: {best} ปี")
        else:
            adjective = "longest" if longest else "shortest"
            lines.append(f"The {adjective} explicitly stated fixed premium-payment option is {names}: {best} years.")
    else:
        lines.append("ไม่พบระยะเวลาชำระเบี้ยแบบกำหนดจำนวนปีที่เพียงพอสำหรับจัดอันดับ" if thai else "The documents do not provide enough fixed payment periods to rank the plans.")
    lines.append("\nระยะเวลาชำระเบี้ยจากเอกสารทุกฉบับ:" if thai else "\nPayment terms across all supplied documents:")
    for t in terms:
        if t.kind == "fixed":
            value = ", ".join(str(y) for y in sorted(set(t.years))) + (" ปี" if thai else " years")
        else:
            labels = {
                "age_based": ("ขึ้นกับอายุเริ่มทำประกันและอายุสิ้นสุดการชำระเบี้ย", "Depends on entry age and the payment-ending age"),
                "renewable": ("สัญญาเพิ่มเติมต่ออายุ ไม่ใช่ระยะเวลาชำระเบี้ยแบบกำหนดจำนวนปี", "Renewable rider; not a fixed payment-year option"),
                "unspecified": ("ยังยืนยันระยะเวลาชำระเบี้ยแบบกำหนดจำนวนปีไม่ได้ จึงไม่รวมในการจัดอันดับ", "Fixed payment years could not be verified; excluded from the ranking"),
            }
            value = labels[t.kind][0 if thai else 1]
        lines.append(f"- {t.product}: {value}. [{t.citation_id}]")
    if any(t.kind != "fixed" for t in terms):
        lines.append("\nการจัดอันดับนี้เปรียบเทียบเฉพาะระยะเวลาที่กำหนดเป็นจำนวนปี แผนที่จ่ายถึงอายุที่กำหนดต้องทราบอายุเริ่มทำประกันก่อน และไม่ใช้ตัวอย่างลูกค้าเป็นระยะเวลาของทุกคน" if thai else "\nThis ranks fixed payment-year options only. Age-based plans require your entry age for a personal comparison; a worked example is not a universal payment duration.")
    lines.append("\nแหล่งข้อมูล:" if thai else "\nSources:")
    for t in terms:
        d = evidence[t.citation_id - 1]
        lines.append(f"[{t.citation_id}] {t.source_file}, page {d.metadata['page']}")
    return "\n".join(lines)
