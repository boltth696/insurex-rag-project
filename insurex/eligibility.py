"""Published entry-age checks, never a guarantee of acceptance."""
import json
import re
from pydantic import BaseModel,Field,model_validator
from .config import ROOT
from .customer_evidence import customer_quote_position


class EntryRange(BaseModel):
    plan: str
    min_years: int = Field(ge=0,le=120)
    max_years: int = Field(ge=0,le=120)

    @model_validator(mode='after')
    def ordered(self):
        if self.min_years>self.max_years:
            raise ValueError('Entry-age range is reversed')
        return self


class EntryProduct(BaseModel):
    product_id: str
    page: int = Field(gt=0)
    variants: list[EntryRange]


def confirmed_integer_age(quote,humans):
    position = customer_quote_position(quote,humans)
    if position<0 or re.search(r'month|days?|เดือน|วัน',quote,re.I):
        return None
    values = re.findall(r'(?<!\d)(\d{1,3})(?!\d|[,.]\d)',quote)
    if len(values)==1:
        age = int(values[0])
        token = rf'{age}(?!\d|[,.]\d)'
    elif not values:
        words=dict(zip('one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(),range(1,20)))
        words.update({'twenty':20,'thirty':30,'forty':40,'fifty':50,'sixty':60,'seventy':70,'eighty':80,'ninety':90})
        parts=re.findall(r'\b(?:'+'|'.join(words)+r')\b',quote,re.I)
        numbers=[words[p.lower()] for p in parts]
        if re.search(r'\bbetween\b|\bto\b|[–—]',quote,re.I) or not (len(numbers)==1 or len(numbers)==2 and numbers[0]>=20 and numbers[0]%10==0 and numbers[1]<=9):
            return None
        age=sum(numbers)
        token='[- ]'.join(re.escape(p) for p in parts)+r'\b'
    else:
        return None
    if not 1<=age<=120:
        return None
    text = str(humans[position].content)
    if re.search(rf'\b(?:age|aged|turned|i am|i[’\x27]m)\s*[:=]?\s*{token}|(?<!\w){token}\s*(?:years? old|y/?o)\b|อายุ\s*{token}',text,re.I):
        return age
    return None


def entry_ranges(catalog):
    rows = [EntryProduct.model_validate(row) for row in json.loads((ROOT/'data/entry_age_ranges.json').read_text(encoding='utf-8'))['products']]
    products = {p.id:p for p in catalog.products}
    if {r.product_id for r in rows}!=set(products) or len(rows)!=len(products):
        raise ValueError('Entry-age notes must cover each catalog product')
    for row in rows:
        if {v.plan for v in row.variants}!={v.plan for v in products[row.product_id].variants}:
            raise ValueError('Entry-age plans do not match the catalog')
    return {r.product_id:r for r in rows}


def age_filtered_candidates(ids,catalog,humans,quote,sources,language):
    age = confirmed_integer_age(quote,humans)
    if age is None:
        return ids,{},[]
    ranges = entry_ranges(catalog)
    products = {p.id:p for p in catalog.products}
    kept,variants,notes = [],{},[]
    thai = language=='Thai'
    for product_id in ids:
        row = ranges[product_id]
        source = next((s for s in sources if s['file']==products[product_id].source_file and s['page']==row.page),None)
        if source is None:
            raise ValueError('Published age check requires its source page')
        allowed = [v.plan for v in row.variants if v.min_years<=age<=v.max_years]
        if allowed:
            kept.append(product_id)
            variants[product_id] = allowed
        if len(allowed)!=len(row.variants):
            limits = '; '.join(f'{v.plan}: '+(('1 เดือน 1 วัน' if thai else '1 month and 1 day') if v.min_years==0 else str(v.min_years))+f'–{v.max_years}' for v in row.variants)
            if allowed:
                text = (f'อายุ {age} ปีอยู่ในช่วงอายุรับประกันที่ระบุของ {products[product_id].name_th} เฉพาะ: '+', '.join(allowed)+' ยังไม่ใช่การยืนยันรับประกัน' if thai else f'At age {age}, only these {products[product_id].name_en} options are within the published entry-age ranges: '+', '.join(allowed)+'. Acceptance remains unverified.')
            else:
                text = (f'อายุ {age} ปีอยู่นอกช่วงอายุรับประกันที่ระบุของ {products[product_id].name_th}: {limits}' if thai else f'Age {age} is outside the published entry-age ranges for {products[product_id].name_en}: {limits}.')
            notes.append(text+f" [{source['id']}]")
    if notes:
        notes.append('ช่วงอายุนี้ใช้สำหรับการสมัครใหม่ ไม่ได้ยืนยันวันสิ้นสุดความคุ้มครองของกรมธรรม์เดิม สัญญาเพิ่มเติมต้องตรวจสอบอายุรับประกันและเงื่อนไขของสัญญานั้นเอง' if thai else 'These are new-application entry-age checks, not the coverage-ending ages of existing policies. Attached riders need their own age and policy terms checked.')
    return kept,variants,notes
