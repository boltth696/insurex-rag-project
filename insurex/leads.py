"""Structured local lead collection and a LangChain SQLite save tool."""
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field, field_validator
from langchain_core.tools import StructuredTool
from .comparison import quote_key
from .customer_evidence import customer_quote_position, contains_customer_quote
from .lead_storage import read_leads


class QuotedValue(BaseModel):
    value: str = Field(description="Customer value, copied from the quoted human text without guessing.")
    quote: str = Field(description="Exact contiguous HUMAN quote supporting this value.")


class LeadTurn(BaseModel):
    action: Literal["collect", "detail", "cancel"] = "collect"
    cancel_quote: str = Field(default="", description="Exact quote from the latest HUMAN message explicitly cancelling or refusing collection. A budget, name or income update is never cancellation.")
    new_customer_quote: str = Field(default="", description="Exact quote from the latest HUMAN message explicitly switching to a different customer. Empty for the same customer's corrections or follow-ups.")
    product_id: str = Field(default="", description="Catalog ID of the explicitly interested product; empty if unclear. Never infer interest from a recommendation or question alone.")
    product_quote: str = Field(default="", description="Exact human quote identifying the interested product.")
    name: QuotedValue | None = None
    occupation: QuotedValue | None = None
    income: QuotedValue | None = Field(default=None, description="Actual income amount and any stated currency/frequency, copied as text. A premium budget is NOT income. Do not invent currency or monthly/yearly frequency.")
    contact_number: QuotedValue | None = None
    query: str = Field(default="", description="Standalone factual question for action=detail; resolve references using only the known interested product. Do not answer it.")


class LeadRecord(BaseModel):
    lead_id: str = Field(min_length=1, max_length=100)
    session_id: str = Field(min_length=1, max_length=200)
    product_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    occupation: str = Field(min_length=1, max_length=300)
    income: str = Field(min_length=1, max_length=300)
    contact_number: str
    evidence: dict[str, str]

    @field_validator("contact_number")
    @classmethod
    def check_phone(cls, value):
        if not re.fullmatch(r"\+?[\d\s().-]+", value.strip()):
            raise ValueError("Use a phone number with digits, optional country code and separators.")
        if not 8 <= len(re.sub(r"\D", "", value)) <= 15:
            raise ValueError("Please check the contact number: expected 8–15 digits.")
        return value.strip()


def lead_interest_intent(question):
    if re.search(r"\b(?:if|suppose|hypothetically)\b|ถ้า|สมมติ", question, re.I):
        return False
    if re.search(r"not interested|don['’]t want|do not want|ไม่สนใจ|ไม่ต้องการ", question, re.I):
        return False
    return bool(re.search(r"\b(?:i(?:['’]m| am)?|we(?:['’]re| are)?)\s+(?:really\s+)?(?:interested|want to (?:buy|apply)|would like to (?:buy|apply))|\binterested in\b|สนใจ|อยากซื้อ|ต้องการสมัคร", question, re.I))


def merge_lead(turn, prior, humans, catalog):
    """Accept only quoted facts from this collection's human messages."""
    draft = dict(prior or {})
    def position(quote):
        return customer_quote_position(quote, humans)
    def supported(value):
        return value and value.value.strip() and contains_customer_quote(value.value, value.quote) and customer_quote_position(value.quote, humans) >= 0
    products = {p.id: p for p in catalog.products}
    if turn.product_id in products and turn.product_quote.strip() and any(quote_key(turn.product_quote) in quote_key(str(m.content)) for m in humans):
        from .catalog import matching_products
        identified = matching_products(catalog, turn.product_quote)
        if len(identified) == 1 and identified[0].id == turn.product_id:
            draft["product_id"] = turn.product_id
            draft["product_quote"] = turn.product_quote
    for field in ("name", "occupation", "income", "contact_number"):
        value = getattr(turn, field)
        if supported(value):
            if field == "income" and re.search(r"budget|buget|งบ", value.quote, re.I) and not re.search(r"income|salary|earn|รายได้|เงินเดือน", value.quote, re.I):
                continue
            if field == "income" and not income_value_is_supported(value):
                continue
            old = draft.get(field)
            if old and position(old["quote"]) > position(value.quote):
                continue
            draft[field] = value.model_dump()
    return draft


def income_value_is_supported(value):
    """A mixed quote cannot make its explicitly labelled budget into income."""
    roles = list(re.finditer(r"budget|buget|spend|premium|income|salary|earn(?:s|ing)?|wages?|รายได้|เงินเดือน|งบ|เบี้ย", value.quote, re.I))
    amounts = re.findall(r"\d[\d,.]*", value.value)
    for amount in amounts:
        occurrence = re.search(re.escape(amount), value.quote)
        if occurrence is None:
            return False
        preceding = [role for role in roles if role.end() <= occurrence.start()]
        if preceding and re.fullmatch(r"budget|buget|spend|premium|งบ|เบี้ย", preceding[-1].group(), re.I):
            return False
    return True


def complete_lead(draft, lead_id, session_id):
    return LeadRecord(lead_id=lead_id, session_id=session_id, product_id=draft["product_id"],
        **{field: draft[field]["value"] for field in ("name", "occupation", "income", "contact_number")},
        evidence={field: draft[field]["quote"] for field in ("name", "occupation", "income", "contact_number")} | {"product": draft["product_quote"]})


def create_lead_tool(database_path: Path):
    """The path comes from app configuration, never from model/tool arguments."""
    database_path = Path(database_path)
    def save_insurance_lead(lead: LeadRecord) -> dict:
        """Save a complete validated insurance lead to local SQLite; retries update the same lead."""
        record = LeadRecord.model_validate(lead)
        database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(database_path)) as connection, connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS leads (
                lead_id TEXT NOT NULL, session_id TEXT NOT NULL, product_id TEXT NOT NULL,
                name TEXT NOT NULL, occupation TEXT NOT NULL, income TEXT NOT NULL,
                contact_number TEXT NOT NULL, structured_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (session_id, lead_id))""")
            connection.execute("""INSERT INTO leads (lead_id,session_id,product_id,name,occupation,income,contact_number,structured_json)
                VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(session_id,lead_id) DO UPDATE SET
                product_id=excluded.product_id, name=excluded.name, occupation=excluded.occupation,
                income=excluded.income, contact_number=excluded.contact_number,
                structured_json=excluded.structured_json, updated_at=CURRENT_TIMESTAMP""",
                (record.lead_id, record.session_id, record.product_id, record.name, record.occupation, record.income, record.contact_number, record.model_dump_json()))
        return {"saved": True, "lead_id": record.lead_id}
    return StructuredTool.from_function(save_insurance_lead)


def lead_prompt(draft, thai=False):
    missing = [f for f in ("product_id", "name", "occupation", "income", "contact_number") if not draft.get(f)]
    labels = {"product_id": "interested product", "name": "name", "occupation": "occupation", "income": "income amount (and currency/monthly or yearly frequency)", "contact_number": "contact number"}
    thai_labels = {"product_id": "ผลิตภัณฑ์ที่สนใจ", "name": "ชื่อ", "occupation": "อาชีพ", "income": "รายได้ พร้อมสกุลเงินและระบุรายเดือนหรือรายปี", "contact_number": "เบอร์ติดต่อ"}
    return ("เข้าสู่โหมดเก็บข้อมูลผู้สนใจ กรุณาระบุ " + ", ".join(thai_labels[f] for f in missing) + " เพื่อบันทึกในฐานข้อมูลภายใน พิมพ์ /cancel-lead เพื่อยกเลิก" if thai else "Lead collection: please provide your " + ", ".join(labels[f] for f in missing) + ". These details will be saved to the local database when complete. Type /cancel-lead to cancel.")
