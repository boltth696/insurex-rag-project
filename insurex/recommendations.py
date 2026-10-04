"""Controlled suitability shortlists: no model-authored prices or rankings."""
import re
from typing import Literal
from pydantic import BaseModel, Field
from .catalog import product_text
from .comparison import quote_key
from .customer_evidence import customer_quote_position, explicit_customer_change


class CustomerNeeds(BaseModel):
    goals: list[Literal["life", "critical_illness", "medical", "savings", "retirement"]] = Field(default_factory=list)
    goal_quote: str = Field(default="", description="Exact contiguous quote from a HUMAN message expressing the latest specific goal; never use assistant suggestions as customer preferences.")
    goal_is_specific: bool = Field(default=True, description="False for broad protection with no indication of death benefits, illness cash or medical bills. True when the meaning supports a specific goal, even using unfamiliar wording.")
    ambiguous_segment: bool = False
    segment: Literal["unknown", "cost_sensitive", "other"] = "unknown"
    segment_quote: str = Field(default="", description="Exact human quote supporting your semantic interpretation of the customer's segment; recognize meaning rather than matching keywords.")
    age_quote: str = Field(default="", description="Exact human quote supplying age or age range, if available.")
    budget_quote: str = Field(default="", description="Exact human quote supplying an affordable premium budget and payment period, if available.")
    benefit_quote: str = Field(default="", description="Exact human quote stating the latest requested benefit amount and event, such as a million baht for family on death. Do not use brochure examples.")
    existing_coverage_quote: str = Field(default="", description="Exact human quote describing existing employer/private insurance, or explicitly no existing cover.")
    coverage_status: Literal["unknown", "none", "current"] = Field(default="unknown", description="none for explicitly no existing insurance; current for existing employer/private cover; unknown if unstated. Must be supported by existing_coverage_quote.")
    new_customer_quote: str = Field(default="", description="Exact quote from the latest human message explicitly switching to a NEW or DIFFERENT customer. Empty for follow-ups about the same customer.")
    question_focus: Literal["general", "family_protection", "existing_coverage"] = "general"
    focus_quote: str = Field(default="", description="Exact human quote supporting the latest family-protection or existing-coverage assessment question.")
    missing_details: list[Literal["age", "budget", "budget_frequency", "existing_coverage"]] = Field(default_factory=list)


def profile_followup(question):
    return bool(re.search(r"budget|buget|protection|income|years? old|\bage\b|medical|critical illness|life cover|death benefit|งบ|อายุ|คุ้มครอง|รายได้|โรคร้ายแรง|ค่ารักษา", question, re.I))


def stated_budget_frequency(quote):
    return bool(re.search(r'\b(?:monthly|yearly|annually|annual|month|year|weekly|week|per annum)\b|/(?:mo|yr)\b|\bp\.a\.|ต่อปี|ต่อเดือน|ปีละ|เดือนละ|รายปี|รายเดือน|รายสัปดาห์|ต่อสัปดาห์',quote,re.I))


def profile_recall_intent(question):
    q = question.lower()
    return bool(re.search(r"(?:have i|i have|did i|i already)\s+(?:told|tell|given|give|mentioned|said)|(?:remember|recall|summari[sz]e|repeat)\s+(?:my|the customer's|what i)|my (?:customer )?profile", q)) or any(t in q for t in ("ฉันบอก", "บอกไปแล้ว", "สรุปข้อมูลของฉัน", "จำข้อมูลของฉัน"))


def budget_fit_intent(question):
    """A current affordability question must outrank historical payment examples."""
    return bool(re.search(r"budget|งบ", question, re.I) and re.search(r"\bfit\b|\bfits\b|\bwithin\b|\bafford\w*\b|อยู่ใน|พอไหม|เพียงพอ", question, re.I))


def render_budget_fit(needs, humans, language):
    thai = language == "Thai"
    text = render_profile(needs, humans, language)
    if 'budget_frequency' in reconcile_known_details(needs,humans).missing_details:
        text += '\n' + ('งบที่ระบุเป็นงบต่อเดือนหรือต่อปี?' if thai else 'Is your stated premium budget monthly or annual?')
    for label, quote in (("ประกันที่มีอยู่" if thai else "Existing insurance", needs.existing_coverage_quote),):
        if customer_quote_position(quote, humans) >= 0:
            text += f"\n- {label}: {quote.strip()}"
    text += ("\n\nยังยืนยันไม่ได้ว่าตัวเลือกใดอยู่ในงบ ต้องมีใบเสนอราคาสำหรับอายุ เพศ ทุนประกัน ผลประโยชน์ และระยะเวลาชำระเบี้ยที่ต้องการ รวมเบี้ยสัญญาเพิ่มเติมที่กำหนด ตัวอย่างเบี้ยของลูกค้าคนละอายุหรือทุนประกันไม่ใช่ใบเสนอราคาของคุณ" if thai else "\n\nI cannot confirm that either option fits your budget without matching quotes for your age, sex, requested death benefit or other coverage, and selected payment term, including required rider premiums. Please obtain comparable quotes for the options being considered. Premium examples for a different age or benefit amount are not quotes for you.")
    return text


def render_profile(needs, humans, language):
    """Recall customer statements, with no insurance recommendations or PDF claims."""
    needs = reconcile_known_details(needs, humans)
    thai = language == "Thai"
    def supported(quote):
        return quote.strip() if customer_quote_position(quote, humans) >= 0 else ("ยังไม่มีข้อมูลที่ยืนยันได้" if thai else "Not verified from your messages")
    labels = ["อายุ", "งบเบี้ย", "เป้าหมายล่าสุด"] if thai else ["Age", "Premium budget", "Latest goal"]
    values = [needs.age_quote, needs.budget_quote, needs.goal_quote]
    heading = "จากข้อมูลที่คุณบอก:" if thai else "From what you told me:"
    text = heading + "\n\n" + "\n".join(f"- {label}: {supported(value)}" for label, value in zip(labels, values))
    if customer_quote_position(needs.benefit_quote, humans) >= 0:
        text += '\n- ' + ('ผลประโยชน์ที่ต้องการ: ' if thai else 'Requested benefit: ') + needs.benefit_quote.strip()
    return text


def merge_customer_profile(needs, previous, humans):
    """Keep verified customer fields between turns; newer quoted facts win."""
    def position(quote):
        return customer_quote_position(quote, humans)
    result = needs.model_copy(deep=True)
    reset = bool(humans) and explicit_customer_change(needs.new_customer_quote, str(humans[-1].content))
    if reset:
        humans = humans[-1:]
        if position(result.goal_quote) < 0:
            result.goal_quote = ""
            result.goals = []
    # Validate incoming fields before recency comparison. A newer quote such
    # as "do not change my income or age" contains no age value and must not
    # overwrite an older verified age, then disappear during validation.
    result = reconcile_known_details(result, humans)
    if previous and not reset:
        prior = CustomerNeeds.model_validate(previous)
        for field in ("age_quote", "budget_quote", "benefit_quote", "existing_coverage_quote"):
            current_quote, old_quote = getattr(result, field), getattr(prior, field)
            if position(old_quote) >= 0 and (position(current_quote) < position(old_quote) or not current_quote.strip()):
                setattr(result, field, old_quote)
                if field == "existing_coverage_quote":
                    result.coverage_status = prior.coverage_status
        # A vague family follow-up does not silently erase an earlier explicit
        # death-benefit goal. It asks whether additional events are wanted.
        family_followup = result.question_focus == "family_protection" and (not result.goal_is_specific or bool(re.search(r"something happens|anything happens|เกิดอะไรขึ้น", result.goal_quote, re.I)))
        if position(prior.goal_quote) >= 0 and (position(result.goal_quote) < position(prior.goal_quote) or not result.goal_quote.strip() or family_followup):
            result.goal_quote = prior.goal_quote
            result.goals = prior.goals
            result.goal_is_specific = prior.goal_is_specific
        # A benefit amount belongs to its stated protection goal. Retain it
        # when adding goals, but do not move an old death benefit to medical
        # cover or illness cash after the customer replaces the goal.
        if (prior.goals and not set(prior.goals).intersection(result.goals)
                and position(result.goal_quote) > position(prior.goal_quote)
                and position(result.benefit_quote) < position(result.goal_quote)):
            result.benefit_quote = ""
    for field in ("age_quote", "budget_quote", "benefit_quote", "existing_coverage_quote", "focus_quote", "segment_quote"):
        if position(getattr(result, field)) < 0:
            setattr(result, field, "")
    if position(result.focus_quote) != len(humans) - 1:
        result.question_focus = "general"
        result.focus_quote = ""
    return reconcile_known_details(result, humans)


def reconcile_known_details(needs, human_messages):
    """Later explicit customer clarifications override stale model flags."""
    result = needs.model_copy(deep=True)
    if human_messages and explicit_customer_change(result.new_customer_quote, str(human_messages[-1].content)):
        human_messages = human_messages[-1:]
    last_ambiguous, last_clarified = -1, -1
    supplied = set()
    latest_explicit_budget = None
    for i, message in enumerate(human_messages):
        text = str(message.content)
        if re.search(r"lower[ -]+mass", text, re.I):
            last_ambiguous = i
        if re.search(r"budget[ -]+con(?:s)?cious|(?:low|lower)[ -]+income|รายได้น้อย|จำกัดงบ|งบน้อย", text, re.I):
            last_clarified = i
        if re.search(r"\b\d{1,3}\s*(?:years? old|y/?o)\b|\bage\s*[:=]?\s*\d{1,3}\b|อายุ\s*\d{1,3}", text, re.I):
            supplied.add("age")
        budget_match = re.search(r"(?:budget|buget|insurance spending limit|งบ)[^\n.!?]{0,40}\d[\d,]*(?:\.\d+)?[^\n.!?]{0,25}(?:year(?:ly)?|month(?:ly)?|annual(?:ly)?|ต่อปี|ต่อเดือน|รายปี|รายเดือน)", text, re.I)
        if budget_match:
            supplied.add("budget")
            if not re.search(r"\b(?:if|suppose|hypothetically)\b|สมมติ|ถ้า", text, re.I):
                latest_explicit_budget = (i, budget_match.group().strip())
    def quote_position(quote):
        return customer_quote_position(quote, human_messages)
    if latest_explicit_budget and latest_explicit_budget[0] > quote_position(result.budget_quote):
        result.budget_quote = latest_explicit_budget[1]
    elif latest_explicit_budget and latest_explicit_budget[0] == quote_position(result.budget_quote) and not stated_budget_frequency(result.budget_quote):
        from .customer_evidence import contains_customer_quote
        if contains_customer_quote(result.budget_quote,latest_explicit_budget[1]):
            result.budget_quote = latest_explicit_budget[1]
    age_value = re.search(r"(?<![\d,.])(?:120|1[01]\d|[1-9]\d?|0)(?![\d,.])|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|twenties|thirties|forties|fifties|sixties)\b|ยี่สิบ|สามสิบ|สี่สิบ|ห้าสิบ|หกสิบ|เจ็ดสิบ|แปดสิบ|เก้าสิบ|หนึ่งร้อย", result.age_quote, re.I)
    age_context = bool(re.search(r"\bage\b|years? old|\by/?o\b|turned|อายุ", result.age_quote, re.I))
    if not age_value or (re.search(r"budget|buget|income|salary|งบ|รายได้|เงินเดือน", result.age_quote, re.I) and not age_context):
        result.age_quote = ""
    # Explicit negative coverage statements must never be rendered as benefits
    # that the customer already has. Semantic status covers other paraphrases.
    if quote_position(result.existing_coverage_quote) >= 0:
        if re.search(r"(?:don['’]t|do not|doesn['’]t|does not) have (?:any )?(?:existing |current )?(?:insurance|cover)|\bno (?:existing |current )?(?:insurance|cover)|ไม่มีประกัน", result.existing_coverage_quote, re.I):
            result.coverage_status = "none"
    else:
        result.coverage_status = "unknown"
    # Explicitly lost/no current cover replaces a stale employer-benefit
    # quotation. A gap for one benefit ("no cover for dental") is different.
    for i, message in enumerate(human_messages):
        text = str(message.content)
        absent = re.search(r"(?:\bno (?:existing |current |other |any )?(?:insurance|cover(?:age)?)(?:\s+(?:now|currently))?(?=\s*[.!?,]|\s*$)|\b(?:don['’]t|do not) have (?:any )?(?:existing |current )?insurance\b|ไม่มีประกัน(?:เดิม|อยู่แล้ว|อยู่)?(?:ตอนนี้)?)", text, re.I)
        if absent and i > quote_position(result.existing_coverage_quote) and not re.search(r'\b(?:if|suppose|hypothetically)\b|สมมติ|ถ้า',text,re.I):
            result.existing_coverage_quote = absent.group().strip()
            result.coverage_status = 'none'
    # 'Cheap' describes price sensitivity, not a usable spending amount.
    if quote_position(result.budget_quote) < 0 or not re.search(r"\d|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|twenty|thirty|forty|fifty|thousand|hundred)\b|พัน|หมื่น|แสน", result.budget_quote, re.I):
        result.budget_quote = ""
        if "budget" not in result.missing_details:
            result.missing_details.append("budget")
    for field, quote in (("age", result.age_quote), ("existing_coverage", result.existing_coverage_quote)):
        if quote_position(quote) < 0 and field not in result.missing_details:
            result.missing_details.append(field)
    # A later broad goal is a new statement, not confirmation of an old
    # specific goal. Override an extractor that cites the old preference.
    latest_broad = None
    for i, message in enumerate(human_messages):
        match = re.search(r"\b(?:(?:the|my|our|their)\s+)?(?:main\s+)?(?:goal|priority|objective)\s*(?:is|:|=)\s*(?:general\s+)?protection\s*(?:[.!?]|$)|(?:เป้าหมายหลัก|เป้าหมาย)\s*(?:คือ|:)\s*(?:ความ)?คุ้มครอง\s*(?:[.!?]|$)", str(message.content), re.I)
        if match:
            latest_broad = (i, match.group(0).strip())
    if latest_broad and latest_broad[0] > quote_position(result.goal_quote):
        result.goals = []
        result.goal_is_specific = False
        result.goal_quote = latest_broad[1]
    if re.search(r'\bprotection\b', result.goal_quote, re.I) and not re.search(r'\b(life|death|die|family|children|dependents?|illness|critical|medical|hospital|health|disability|accident|cancer|savings|retirement)\b', result.goal_quote, re.I):
        result.goals = []
        result.goal_is_specific = False
    if human_messages:
        latest = str(human_messages[-1].content)
        if re.search(r'something happens|anything happens|เกิดอะไรขึ้น', latest, re.I) and re.search(r'children|kids|family|dependents?|ครอบครัว|ลูก', latest, re.I):
            result.question_focus = 'family_protection'
            result.focus_quote = latest
    # Semantic fields are accepted only with customer-message evidence. There
    # is no required synonym list: the model can interpret unfamiliar wording.
    if result.segment != "unknown":
        semantic_position = quote_position(result.segment_quote)
        if semantic_position >= 0:
            last_clarified = max(last_clarified, semantic_position)
    for field, quote in (("age", result.age_quote), ("budget", result.budget_quote), ("existing_coverage", result.existing_coverage_quote)):
        if quote_position(quote) >= 0:
            supplied.add(field)
    if last_clarified >= 0 and last_clarified >= last_ambiguous:
        result.ambiguous_segment = False
    # A vague segment label is not essential once concrete needs are given.
    # Use the actual age, budget and goal instead of repeatedly asking what
    # an earlier marketing label means.
    concrete_position = max((i for i, m in enumerate(human_messages) if profile_followup(str(m.content))), default=-1)
    goal_supplied = quote_position(result.goal_quote) >= 0 or any(re.search(r"(?:main\s+)?goal|protection|เป้าหมาย|คุ้มครอง", str(m.content), re.I) for m in human_messages[last_ambiguous if last_ambiguous >= 0 else 0:])
    if {"age", "budget"} <= supplied and goal_supplied and concrete_position >= last_ambiguous:
        result.ambiguous_segment = False
    # An old or invented segment label must not hijack a new generic request.
    if not human_messages or not re.search(r"lower[ -]+mass", str(human_messages[-1].content), re.I):
        result.ambiguous_segment = False
    result.missing_details = [d for d in result.missing_details if d not in supplied and d != 'budget_frequency']
    if result.budget_quote and not stated_budget_frequency(result.budget_quote):
        result.missing_details.append('budget_frequency')
    return result


def render_recommendation(needs, catalog, human_messages, sources, language):
    needs = reconcile_known_details(needs, human_messages)
    thai = language == "Thai"
    if needs.goals and customer_quote_position(needs.goal_quote, human_messages) < 0:
        raise ValueError("Customer goal must be supported by a human-message quote.")
    # Let semantic extraction handle paraphrases. Retain a narrow guard for
    # the observed failure of treating bare "protection" as a life preference.
    bare_protection = bool(re.search(r"(?:^|(?:main\s+)?goal\s*(?:is|:))\s*(?:general\s+)?protection[.!\s]*$", needs.goal_quote, re.I))
    goals = needs.goals if needs.goal_is_specific and not bare_protection else []
    focus_supported = customer_quote_position(needs.focus_quote, human_messages) >= 0
    def missing_request(include_benefit=False):
        fields = [f for f in ("age", "budget", "budget_frequency") if f in needs.missing_details]
        labels = {"age": "อายุ" if thai else "age", "budget": "งบเบี้ย" if thai else "premium budget", "budget_frequency": "งบเป็นต่อเดือนหรือต่อปี" if thai else "whether your stated budget is monthly or annual"}
        missing = [labels[f] for f in fields]
        if include_benefit and customer_quote_position(needs.benefit_quote, human_messages) < 0:
            missing.append("จำนวนเงินที่อยากให้ครอบครัวได้รับ" if thai else "the amount you want your family to receive")
        return ((" ขอข้อมูลเพิ่ม: " if thai else " Please provide your ") + ", ".join(missing) + ".") if missing else ""
    def known_profile():
        if not any((needs.age_quote, needs.budget_quote, needs.benefit_quote)):
            return ""
        return "\n\n" + ("จากข้อมูลที่คุณบอก:" if thai else "From what you told me:") + "\n" + "\n".join(
            f"- {label}: {quote}" for label, quote in (("อายุ" if thai else "Age", needs.age_quote), ("งบเบี้ย" if thai else "Premium budget", needs.budget_quote), ("ผลประโยชน์ที่ต้องการ" if thai else "Requested benefit", needs.benefit_quote))
            if customer_quote_position(quote, human_messages) >= 0)
    if focus_supported and needs.question_focus == "existing_coverage":
        if needs.coverage_status == "none":
            return ("คุณระบุว่ายังไม่มีประกัน ต้องการความคุ้มครองแบบใดเพิ่มเติม?" if thai else "You said you have no existing insurance. What protection do you want to arrange?") + known_profile() + missing_request()
        return ("ควรตรวจสอบความคุ้มครองที่มีอยู่ วงเงิน ข้อยกเว้น และส่วนที่ยังขาดก่อน ไม่จำเป็นต้องซื้อเพิ่มโดยอัตโนมัติ สวัสดิการบริษัทครอบคลุมอะไร วงเงินและค่าห้องเท่าไร และเปลี่ยนอย่างไรเมื่อออกจากงาน? ยังยืนยันไม่ได้ว่าแผนใดอยู่ในงบจนกว่าจะมีใบเสนอราคา" if thai else "Extra insurance is not automatically necessary. First check your existing coverage's benefits, limits, exclusions and gaps, including what happens to employer benefits when you leave the job. What are its annual and room limits, and what additional protection do you want? A matching quote is needed before confirming budget fit.") + known_profile() + missing_request()
    vague_family = "life" in needs.goals and bool(re.search(r"something happens|anything happens|เกิดอะไรขึ้น", needs.goal_quote, re.I))
    explicit_death_focus = bool(re.search(r'\b(?:die|death|death benefit)\b|เสียชีวิต',needs.focus_quote,re.I))
    if (focus_supported and needs.question_focus == "family_protection" and not explicit_death_focus) or vague_family:
        if "life" in goals and not vague_family:
            text = "คุณระบุเป้าหมายเงินให้ครอบครัวเมื่อเสียชีวิตแล้ว ต้องการเพิ่มความคุ้มครองทุพพลภาพหรือเจ็บป่วยด้วยไหม? ไม่ควรถือว่าประกันหนึ่งแผนจ่ายทุกเหตุการณ์" if thai else "You previously stated a death-benefit goal for your family. Do you also want support if you become disabled or ill? I cannot assume one policy pays for every event."
        else:
            text = "คุณต้องการเงินให้ลูกหรือครอบครัวหากเกิดเหตุ ต้องการเงินเมื่อเสียชีวิต หรือกรณีทุพพลภาพหรือเจ็บป่วย? ไม่ควรถือว่าประกันหนึ่งแผนจ่ายทุกเหตุการณ์" if thai else "You want money for your children or family if something happens to you. Is the priority a death benefit for them, or support if you become disabled or ill? These events need different benefits; I cannot assume one policy pays for every event."
        return text + known_profile() + missing_request(include_benefit=True) + (" ต้องมีใบเสนอราคาเพื่อยืนยันว่าอยู่ในงบ" if thai else " Budget fit needs a matching quote.")
    # Marketing/income segment labels are optional context, never a prerequisite
    # for suitability and never a basis for inferring a budget or benefit need.
    if not goals:
        protection_stated = any(re.search(r"\bprotection\b|คุ้มครอง", str(m.content), re.I) and not profile_recall_intent(str(m.content)) for m in human_messages)
        if not protection_stated:
            missing = []
            if customer_quote_position(needs.age_quote, human_messages) < 0:
                missing.append("อายุ" if thai else "age")
            if customer_quote_position(needs.budget_quote, human_messages) < 0:
                missing.append("งบเบี้ยต่อเดือนหรือต่อปี" if thai else "monthly or annual premium budget")
            elif 'budget_frequency' in needs.missing_details:
                missing.append("งบเป็นต่อเดือนหรือต่อปี" if thai else "whether your stated budget is monthly or annual")
            missing.append("เป้าหมายหลัก เช่น ความคุ้มครอง ค่ารักษาพยาบาล การออม หรือเกษียณ" if thai else "main goal: life protection, critical illness cash, medical bills, savings or retirement")
            return (("ช่วยบอก " if thai else "To suggest suitable products, please tell me your ") + "; ".join(missing) + (" ยังยืนยันไม่ได้ว่าแผนใดอยู่ในงบจนกว่าจะมีใบเสนอราคาที่ตรงกับข้อมูลของคุณ" if thai else ". Budget fit needs a quote matching your profile and requested coverage."))
        return ("ต้องการความคุ้มครองแบบไหนเป็นหลัก: เงินให้ครอบครัวเมื่อเสียชีวิต เงินก้อนเมื่อเจ็บป่วยโรคร้ายแรง หรือค่ารักษาพยาบาล? ยังยืนยันไม่ได้ว่าแผนใดอยู่ในงบจนกว่าจะมีใบเสนอราคาสำหรับลูกค้าและความคุ้มครองที่ต้องการ" if thai else "What kind of protection is the priority: money for family on death, a lump sum for critical illness, or medical bills? A broad protection goal is not enough to choose one product. Budget fit remains unverified until there is a quote for this customer's profile and requested coverage.")
    mapping = {"life": ["cheeva", "ci_plus"], "critical_illness": ["ci_plus", "cheeva"], "medical": ["raksa"], "savings": ["aomsook"], "retirement": ["bamnan"]}
    ids = list(dict.fromkeys(pid for goal in goals for pid in mapping[goal]))
    products = {p.id: p for p in catalog.products}
    from .eligibility import age_filtered_candidates
    original_ids = set(ids)
    ids,allowed_variants,age_notes = age_filtered_candidates(ids,catalog,human_messages,needs.age_quote,sources,language)
    lines = ["ตัวเลือกเบื้องต้นตามเป้าหมายที่ระบุ (ยังไม่ใช่การยืนยันว่าอยู่ในงบ):" if thai else "Candidates to compare for your stated goal; affordability is not yet verified:"]
    lines.extend(age_notes)
    if not ids:
        lines.append('ยังไม่มีตัวเลือกตามเป้าหมายที่อยู่ในช่วงอายุรับประกันจากเอกสารที่ให้มา ควรสอบถามผู้รับประกันเกี่ยวกับทางเลือกอื่น ไม่ใช่การยืนยันว่าไม่สามารถซื้อประกันใดๆ ได้' if thai else 'None of the goal-matched options in these brochures is within the published entry-age range for this age. Ask the insurer about other products; this does not establish that insurance elsewhere is unavailable.')
    if "life" in goals:
        lines.append("สำหรับเป้าหมายเงินให้ครอบครัวเมื่อเสียชีวิต ควรเปรียบเทียบผลประโยชน์เสียชีวิตและทุนประกันที่ต้องการ ไม่ใช่ถือว่าจ่ายทุกเหตุการณ์" if thai else "For money to your family on death, compare death benefits and the amount your dependents need. This does not establish payment for every unexpected event.")
    if customer_quote_position(needs.existing_coverage_quote, human_messages) >= 0:
        if needs.coverage_status == "none":
            lines.append("คุณระบุว่ายังไม่มีประกัน" if thai else "You said you have no existing insurance.")
        else:
            lines.append("คุณระบุข้อมูลประกันแล้ว หากมีประกันหรือสวัสดิการอยู่ ควรตรวจสอบความคุ้มครอง วงเงิน และส่วนที่ยังขาดก่อนซื้อเพิ่ม" if thai else "You have described your insurance situation. If you have existing coverage, check its benefits, limits and gaps before adding insurance. Extra insurance is not automatically necessary.")
    for pid in ids:
        p = products[pid]
        if pid in allowed_variants:
            p = p.model_copy(update={'variants':[v for v in p.variants if v.plan in allowed_variants[pid]]})
        citations = [s for s in sources if s["file"] == p.source_file]
        if not citations:
            raise ValueError("Candidate is missing retrieved source evidence.")
        lines.append("\n" + product_text(p, language) + " " + " ".join(f"[{s['id']}]" for s in citations))
        if pid == "cheeva":
            lines.append("ซีไอ 50 เป็นหนึ่งในตัวเลือกสัญญาเพิ่มเติมตามเงื่อนไข ไม่ได้รวมในทุกแผนโดยอัตโนมัติ ระยะเวลาชำระเบี้ยและความคุ้มครองของสัญญาหลักไม่ควรนำไปใช้กับสัญญาเพิ่มเติมโดยอัตโนมัติ" if thai else "CI 50 is one eligible attached-rider choice under the brochure's requirements; it is not automatically included in every policy. Base-policy payment and coverage terms do not automatically apply to riders.")
        if pid == "raksa":
            lines.append("เป็นสัญญาเพิ่มเติม ต้องพิจารณากรมธรรม์หลักที่เข้าเงื่อนไขและเบี้ยรวมด้วย" if thai else "This is a health rider: check the eligible base life policy and its premium as part of the total cost.")
    lines.append("\nยังไม่มีใบเสนอราคาที่เทียบกันสำหรับลูกค้าคนนี้ จึงยืนยันไม่ได้ว่าแผนใดอยู่ในงบหรือถูกกว่า ระยะเวลาจ่ายเบี้ยที่สั้นกว่าและตัวเลือกจ่ายรายเดือนไม่ได้พิสูจน์ว่าเบี้ยถูกกว่า" if thai else "No comparable quotes for this customer have been verified, so I cannot confirm that any candidate fits the budget or costs less. Shorter payment periods and monthly payment options do not establish affordability.")
    labels = {"age": "age", "budget": "monthly or annual premium budget", "budget_frequency": "whether your stated budget is monthly or annual", "existing_coverage": "existing insurance coverage"}
    if needs.missing_details:
        lines.append(("ขอข้อมูลเพิ่มเติม: " + ", ".join({"age": "อายุ", "budget": "งบเบี้ยต่อเดือนหรือต่อปี", "budget_frequency": "งบเป็นต่อเดือนหรือต่อปี", "existing_coverage": "ประกันที่มีอยู่"}[x] for x in dict.fromkeys(needs.missing_details))) if thai else "Please provide: " + ", ".join(labels[x] for x in dict.fromkeys(needs.missing_details)) + ".")
    lines.append("ควรเปรียบเทียบใบเสนอราคาด้วยทุนประกันและความคุ้มครองที่ต้องการ รวมเบี้ยสัญญาเพิ่มเติม และตรวจสอบเงื่อนไขการรับประกันภัย" if thai else "Next, compare quotes for the requested benefit amounts and coverage, including rider premiums, and check underwriting eligibility.")
    used = [s for s in sources if s["file"] in {products[pid].source_file for pid in original_ids}]
    lines.append("\nSources:\n" + "\n".join(f"[{s['id']}] {s['file']}, page {s['page']}" for s in used))
    return "\n".join(lines)
