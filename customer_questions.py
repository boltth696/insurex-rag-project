"""Useful clarifications for factual questions with no selected product.

These responses avoid inventing contract terms or a customer's eligibility.
Named product questions continue to the source-backed answer path.
"""


def clarify_unscoped(topic, language):
    english = {
        "missed_payment": "Which product or policy are you considering? I cannot confirm the consequences of a missed payment without its payment and policy terms. Check the applicable grace period, lapse/reinstatement rules and any rider consequences before relying on coverage. I cannot assume you can pause premiums without affecting coverage.",
        "eligibility": "I cannot confirm acceptance or rejection from a medical condition alone. Which product are you considering, and what is your age? Disclose the condition accurately in the application; eligibility and any special terms need the insurer's underwriting assessment. I cannot promise coverage for an existing condition.",
        "waiting": "I cannot confirm that an illness next month would be covered without the product, illness/benefit and coverage start date. Waiting periods and exclusions vary by benefit. Which product are you considering, and what type of illness or claim do you mean?",
        "exclusions": "Which product or rider do you mean? Exclusions differ between these policies and benefits. Once you specify the product, I can explain the exclusions stated in its brochure and identify any details that need the full policy wording.",
        "cancellation": "I cannot calculate a refund after two years from that information alone. Which product, payment term and sum insured do you have? The policy's applicable surrender/cancellation terms and value schedule are needed. Do not assume cancellation returns all premiums paid.",
        "coverage_duration": "Not necessarily: finishing premium payments and the end of coverage are different dates. Which product and payment option do you mean? I can check its stated coverage duration; rider terms must be checked separately rather than inheriting the main policy's payment period.",
        "medical_scope": "Which health product and plan do you mean? Private-hospital treatment and single-room costs must be checked against the selected plan's room benefit, limits, deductible and policy conditions. I cannot promise every private hospital or the full room bill is covered without those details.",
        "cancer_payment": "The answer depends on the product/rider and qualifying cancer stage: some benefits provide a cash lump sum, while medical-expense benefits reimburse eligible treatment costs under their limits. Which product or rider are you asking about? I can then check the benefit type, conditions and waiting periods in its brochure.",
    }
    thai = {
        "missed_payment": "หมายถึงผลิตภัณฑ์หรือกรมธรรม์ไหน? ยังยืนยันผลของการขาดชำระเบี้ยไม่ได้จนกว่าจะตรวจสอบเงื่อนไข เช่น ระยะผ่อนผัน การสิ้นผลบังคับ การต่ออายุกรมธรรม์ และผลต่อสัญญาเพิ่มเติม ไม่ควรถือว่าหยุดจ่ายเบี้ยแล้วความคุ้มครองยังเหมือนเดิม",
        "eligibility": "ยังยืนยันการรับประกันหรือปฏิเสธไม่ได้จากโรคประจำตัวเพียงอย่างเดียว สนใจแผนไหนและอายุเท่าไร? ต้องแถลงสุขภาพตามจริง และให้บริษัทประเมินการรับประกันกับเงื่อนไขเฉพาะ ยังรับรองความคุ้มครองโรคที่เป็นอยู่ไม่ได้",
        "waiting": "ยังยืนยันไม่ได้ว่าป่วยเดือนหน้าจะเคลมได้ ต้องทราบแผนประกัน ประเภทโรคหรือผลประโยชน์ และวันเริ่มคุ้มครองก่อน ระยะรอคอยและข้อยกเว้นต่างกันตามผลประโยชน์ สนใจแผนไหนและกรณีป่วยแบบใด?",
        "exclusions": "หมายถึงผลิตภัณฑ์หรือสัญญาเพิ่มเติมไหน? ข้อยกเว้นต่างกันตามแผนและผลประโยชน์ เมื่อระบุแผนแล้วจะตรวจสอบข้อยกเว้นที่มีในโบรชัวร์และส่วนที่ต้องดูกรมธรรม์ฉบับเต็มให้",
        "cancellation": "ยังคำนวณเงินคืนหลังสองปีไม่ได้จากข้อมูลนี้ ขอชื่อแผน ระยะเวลาชำระเบี้ย และทุนประกันก่อน ต้องตรวจสอบเงื่อนไขยกเลิกหรือเวนคืนและตารางมูลค่าตามกรมธรรม์ ไม่ควรถือว่าจะได้เงินคืนเท่ากับเบี้ยทั้งหมดที่จ่าย",
        "coverage_duration": "ไม่จำเป็นต้องสิ้นสุดพร้อมกัน ระยะเวลาชำระเบี้ยกับระยะเวลาคุ้มครองเป็นคนละเรื่อง หมายถึงแผนและตัวเลือกชำระเบี้ยไหน? ต้องตรวจสอบระยะคุ้มครองที่ระบุและเงื่อนไขสัญญาเพิ่มเติมแยกจากสัญญาหลัก",
        "medical_scope": "หมายถึงประกันสุขภาพและแผนไหน? ต้องตรวจสอบค่าห้อง วงเงิน ความรับผิดส่วนแรก และเงื่อนไขของแผน ยังรับรองไม่ได้ว่าจะครอบคลุมทุกโรงพยาบาลเอกชนหรือค่าห้องเดี่ยวเต็มจำนวน",
        "cancer_payment": "ขึ้นอยู่กับผลิตภัณฑ์หรือสัญญาเพิ่มเติมและระยะโรคมะเร็งที่เข้าเงื่อนไข บางผลประโยชน์จ่ายเงินก้อน ส่วนค่ารักษาจ่ายตามค่าใช้จ่ายที่เข้าเงื่อนไขภายในวงเงิน หมายถึงแผนไหน? จะตรวจสอบประเภทผลประโยชน์ เงื่อนไข และระยะรอคอยให้",
    }
    return (thai if language == "Thai" else english)[topic]
