"""Controlled answers for a reviewed table qualification prone to inversion."""
import json
import re
from pydantic import BaseModel, Field
from .config import ROOT
from .catalog import matching_products


class DeductibleScope(BaseModel):
    amount: int = Field(gt=0)
    page: int = Field(gt=0)
    exceptions: list[str]


def reviewed_deductible_scope(query, sources, catalog, language):
    named = matching_products(catalog, query)
    if {p.id for p in named} != {'raksa'}:
        return None
    q = query.lower()
    if not re.search(r'deductible|ความรับผิดส่วนแรก',q) or re.search(r'premium|price|cheaper|เบี้ย',q):
        return None
    if not re.search(r'scope|every(?:thing| benefit)|all benefits?|entire year|whole year|once.{0,12}year|per.{0,15}admission|each.{0,15}admission|per year|ทุก|ทั้งปี|ต่อครั้ง|ครั้งเดียว|ยกเว้น',q):
        return None
    facts = DeductibleScope.model_validate(json.loads((ROOT/'data/deductible_scope.json').read_text(encoding='utf-8')))
    source = next((s for s in sources if s['file']==named[0].source_file and s['page']==facts.page),None)
    if source is None:
        return None
    if language == 'Thai':
        text = f'ความรับผิดส่วนแรก {facts.amount:,} บาทคิดต่อการเข้ารักษาเป็นผู้ป่วยในแต่ละครั้ง ไม่ใช่ครั้งเดียวต่อปี ใช้กับผลประโยชน์ข้อ 1–6 ตามเงื่อนไข โดยยกเว้นข้อ 2.1, ข้อ 2.2 เฉพาะค่าผ่าตัดเล็ก (Minor Surgery), ข้อ 3.1 และข้อ 6.1 ไม่ควรถือว่าข้อ 2.2 ทั้งหมดได้รับยกเว้น โปรดตรวจสอบเงื่อนไขฉบับเต็มสำหรับการเคลมจริง'
    else:
        text = f'The THB {facts.amount:,} deductible applies per inpatient admission, not once for the entire year. It applies to benefits 1–6 subject to the printed exceptions: ' + '; '.join(facts.exceptions) + '. Only the minor-surgery part of benefit 2.2 is listed as an exception; do not exempt the entire day-surgery benefit or reverse this into excluding minor surgery from the exception. It does not apply to every benefit. Full policy and claim conditions still apply.'
    return text+f"\n\nSources:\n[{source['id']}] {source['file']}, page {source['page']}"
