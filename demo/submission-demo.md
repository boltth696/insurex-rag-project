# Live submission demo log

Recorded: 2026-10-04T09:44:11.666545+07:00

Actual application output using synthetic customers and temporary SQLite databases.

Checks: 26/26.

## 1. All five brochures

Session: `demo-catalog`

Result: PASS

Customer:

What products are available?

Assistant (verbatim):

The supplied brochures describe these 5 product families:

1. Khum Cheeva / คุ้มชีวา (90/10): Life insurance with additional rider options. Coverage: until age 90. Premium payments: 10 years, depending on the variant. [1]

2. Khum Bamnan / คุ้มบำนาญ (85/55, 85/60, 85/65): Pension insurance. Coverage: until age 85. Premium payments: 85/55: until age 55; 85/60: until age 60; 85/65: until age 65. [2]

3. Khum Raksa Maojai Extra / คุ้มรักษา เหมาจ่าย เอ็กซ์ตร้า (Extra): Health insurance rider; benefits depend on the selected plan. Coverage: until age 99, or the base life policy's coverage term if shorter, subject to conditions. The brochure does not specify a fixed number of premium-payment years. [3]

4. Khum Aomsook / คุ้มออมสุข (25/15): Savings insurance. Coverage: 25 years. Premium payments: 15 years, depending on the variant. [4]

5. Khum Talodcheep CI Plus / คุ้มตลอดชีพ ซีไอ พลัส (90/5, 90/10, 90/20): Life and critical illness insurance. Coverage: until age 90. Premium payments: 5, 10, 20 years, depending on the variant. [5]


Sources:

[1] 02_SCB-InsureX_Khum-Cheeva_90-10_180669.pdf, pages 1, 3

[2] 05_SCB-InsureX_Khum-Bamnan_85-55_85-60_85-65_180669.pdf, pages 1, 4

[3] 07_SCB-InsureX_Khum-Raksa-Maojai-Extra_180669.pdf, pages 1, 4

[4] 09_SCB-InsureX_Khum-Aomsook_25-15_180669.pdf, pages 1, 2

[5] 11_SCB-InsureX_Khum-Talodcheep-CI-Plus_90-5_90-10_90-20_180669.pdf, pages 1, 3

Executed nodes: `rewrite → catalog_answer`

## 2. Shortest fixed premium period

Session: `demo-catalog`

Result: PASS

Customer:

Which product has the shortest premium-payment period?

Assistant (verbatim):

The shortest fixed premium-payment option is คุ้มตลอดชีพ ซีไอ พลัส 90/5: 5 years.

The supplied brochures describe these 5 product families:

1. Khum Cheeva / คุ้มชีวา (90/10): Life insurance with additional rider options. Coverage: until age 90. Premium payments: 10 years, depending on the variant. [1]

2. Khum Bamnan / คุ้มบำนาญ (85/55, 85/60, 85/65): Pension insurance. Coverage: until age 85. Premium payments: 85/55: until age 55; 85/60: until age 60; 85/65: until age 65. [2]

3. Khum Raksa Maojai Extra / คุ้มรักษา เหมาจ่าย เอ็กซ์ตร้า (Extra): Health insurance rider; benefits depend on the selected plan. Coverage: until age 99, or the base life policy's coverage term if shorter, subject to conditions. The brochure does not specify a fixed number of premium-payment years. [3]

4. Khum Aomsook / คุ้มออมสุข (25/15): Savings insurance. Coverage: 25 years. Premium payments: 15 years, depending on the variant. [4]

5. Khum Talodcheep CI Plus / คุ้มตลอดชีพ ซีไอ พลัส (90/5, 90/10, 90/20): Life and critical illness insurance. Coverage: until age 90. Premium payments: 5, 10, 20 years, depending on the variant. [5]


Sources:

[1] 02_SCB-InsureX_Khum-Cheeva_90-10_180669.pdf, pages 1, 3

[2] 05_SCB-InsureX_Khum-Bamnan_85-55_85-60_85-65_180669.pdf, pages 1, 4

[3] 07_SCB-InsureX_Khum-Raksa-Maojai-Extra_180669.pdf, pages 1, 4

[4] 09_SCB-InsureX_Khum-Aomsook_25-15_180669.pdf, pages 1, 2

[5] 11_SCB-InsureX_Khum-Talodcheep-CI-Plus_90-5_90-10_90-20_180669.pdf, pages 1, 3

This ranks fixed payment-year options only. Pension payment durations depend on your entry age; the health rider has no stated fixed payment-year period. These are not ranked as fixed-year plans.

Executed nodes: `rewrite → catalog_answer`

## 3. Customer A life goal

Session: `demo-a`

Result: PASS

Customer:

I am a frugal customer, age 22. Annual insurance budget 20000 THB. I want my family to receive money if I die. No existing insurance.

Assistant (verbatim):

Candidates to compare for your stated goal; affordability is not yet verified:
For money to your family on death, compare death benefits and the amount your dependents need. This does not establish payment for every unexpected event.
You said you have no existing insurance.

Khum Cheeva / คุ้มชีวา (90/10): Life insurance with additional rider options. Coverage: until age 90. Premium payments: 10 years, depending on the variant. [1] [2] [3]
CI 50 is one eligible attached-rider choice under the brochure's requirements; it is not automatically included in every policy. Base-policy payment and coverage terms do not automatically apply to riders.

Khum Talodcheep CI Plus / คุ้มตลอดชีพ ซีไอ พลัส (90/5, 90/10, 90/20): Life and critical illness insurance. Coverage: until age 90. Premium payments: 5, 10, 20 years, depending on the variant. [14] [15] [16]
No comparable quotes for this customer have been verified, so I cannot confirm that any candidate fits the budget or costs less. Shorter payment periods and monthly payment options do not establish affordability.
Next, compare quotes for the requested benefit amounts and coverage, including rider premiums, and check underwriting eligibility.

Sources:
[1] 02_SCB-InsureX_Khum-Cheeva_90-10_180669.pdf, page 1
[2] 02_SCB-InsureX_Khum-Cheeva_90-10_180669.pdf, page 2
[3] 02_SCB-InsureX_Khum-Cheeva_90-10_180669.pdf, page 3
[14] 11_SCB-InsureX_Khum-Talodcheep-CI-Plus_90-5_90-10_90-20_180669.pdf, page 1
[15] 11_SCB-InsureX_Khum-Talodcheep-CI-Plus_90-5_90-10_90-20_180669.pdf, page 2
[16] 11_SCB-InsureX_Khum-Talodcheep-CI-Plus_90-5_90-10_90-20_180669.pdf, page 3

Executed nodes: `rewrite → retrieve → recommend`

## 4. Customer B medical goal

Session: `demo-b`

Result: PASS

Customer:

I am age 45. Annual insurance budget 60000 THB. I want help paying hospital bills. No existing insurance.

Assistant (verbatim):

Candidates to compare for your stated goal; affordability is not yet verified:
You said you have no existing insurance.

Khum Raksa Maojai Extra / คุ้มรักษา เหมาจ่าย เอ็กซ์ตร้า (Extra): Health insurance rider; benefits depend on the selected plan. Coverage: until age 99, or the base life policy's coverage term if shorter, subject to conditions. The brochure does not specify a fixed number of premium-payment years. [8] [9] [10] [11]
This is a health rider: check the eligible base life policy and its premium as part of the total cost.
No comparable quotes for this customer have been verified, so I cannot confirm that any candidate fits the budget or costs less. Shorter payment periods and monthly payment options do not establish affordability.
Next, compare quotes for the requested benefit amounts and coverage, including rider premiums, and check underwriting eligibility.

Sources:
[8] 07_SCB-InsureX_Khum-Raksa-Maojai-Extra_180669.pdf, page 1
[9] 07_SCB-InsureX_Khum-Raksa-Maojai-Extra_180669.pdf, page 2
[10] 07_SCB-InsureX_Khum-Raksa-Maojai-Extra_180669.pdf, page 3
[11] 07_SCB-InsureX_Khum-Raksa-Maojai-Extra_180669.pdf, page 4

Executed nodes: `rewrite → retrieve → recommend`

## 5. Customer A recall stays separate

Session: `demo-a`

Result: PASS

Customer:

What age, annual budget and goal have I told you?

Assistant (verbatim):

From what you told me:

- Age: age 22
- Premium budget: Annual insurance budget 20000 THB
- Latest goal: I want my family to receive money if I die

Executed nodes: `rewrite → recommend`

## 6. Explicit interest activates tooling

Session: `demo-a`

Result: PASS

Customer:

I am interested in Khum Cheeva.

Assistant (verbatim):

Lead collection: please provide your name, occupation, income amount (and currency/monthly or yearly frequency), contact number. These details will be saved to the local database when complete. Type /cancel-lead to cancel.

Executed nodes: `rewrite → collect_lead`

## 7. Collect only supplied fields

Session: `demo-a`

Result: PASS

Customer:

My name is Demo Alex. I am a student. My income is 20,000 THB per month. My insurance budget is 20000 THB per year.

Assistant (verbatim):

Lead collection: please provide your contact number. These details will be saved to the local database when complete. Type /cancel-lead to cancel.

Executed nodes: `rewrite → collect_lead`

## 8. Independent process restores draft

Session: `demo-a`

Result: PASS

Observed saved data:

```json
{
  "history": [
    [
      "user",
      "I am a frugal customer, age 22. Annual insurance budget 20000 THB. I want my family to receive money if I die. No existing insurance."
    ],
    [
      "assistant",
      "Candidates to compare for your stated goal; affordability is not yet verified:\nFor money to your family on death, compare death benefits and the amount your dependents need. This does not establish payment for every unexpected event.\nYou said you have no existing insurance.\n\nKhum Cheeva / คุ้มชีวา (90/10): Life insurance with additional rider options. Coverage: until age 90. Premium payments: 10 years, depending on the variant. [1] [2] [3]\nCI 50 is one eligible attached-rider choice under the brochure's requirements; it is not automatically included in every policy. Base-policy payment and coverage terms do not automatically apply to riders.\n\nKhum Talodcheep CI Plus / คุ้มตลอดชีพ ซีไอ พลัส (90/5, 90/10, 90/20): Life and critical illness insurance. Coverage: until age 90. Premium payments: 5, 10, 20 years, depending on the variant. [14] [15] [16]\nNo comparable quotes for this customer have been verified, so I cannot confirm that any candidate fits the budget or costs less. Shorter payment periods and monthly payment options do not establish affordability.\nNext, compare quotes for the requested benefit amounts and coverage, including rider premiums, and check underwriting eligibility.\n\nSources:\n[1] 02_SCB-InsureX_Khum-Cheeva_90-10_180669.pdf, page 1\n[2] 02_SCB-InsureX_Khum-Cheeva_90-10_180669.pdf, page 2\n[3] 02_SCB-InsureX_Khum-Cheeva_90-10_180669.pdf, page 3\n[14] 11_SCB-InsureX_Khum-Talodcheep-CI-Plus_90-5_90-10_90-20_180669.pdf, page 1\n[15] 11_SCB-InsureX_Khum-Talodcheep-CI-Plus_90-5_90-10_90-20_180669.pdf, page 2\n[16] 11_SCB-InsureX_Khum-Talodcheep-CI-Plus_90-5_90-10_90-20_180669.pdf, page 3"
    ],
    [
      "user",
      "What age, annual budget and goal have I told you?"
    ],
    [
      "assistant",
      "From what you told me:\n\n- Age: age 22\n- Premium budget: Annual insurance budget 20000 THB\n- Latest goal: I want my family to receive money if I die"
    ],
    [
      "user",
      "I am interested in Khum Cheeva."
    ],
    [
      "assistant",
      "Lead collection: please provide your name, occupation, income amount (and currency/monthly or yearly frequency), contact number. These details will be saved to the local database when complete. Type /cancel-lead to cancel."
    ],
    [
      "user",
      "My name is Demo Alex. I am a student. My income is 20,000 THB per month. My insurance budget is 20000 THB per year."
    ],
    [
      "assistant",
      "Lead collection: please provide your contact number. These details will be saved to the local database when complete. Type /cancel-lead to cancel."
    ]
  ],
  "profile": {
    "goals": [
      "life"
    ],
    "goal_quote": "I want my family to receive money if I die",
    "goal_is_specific": true,
    "ambiguous_segment": false,
    "segment": "cost_sensitive",
    "segment_quote": "I am a frugal customer",
    "age_quote": "age 22",
    "budget_quote": "Annual insurance budget 20000 THB",
    "benefit_quote": "",
    "existing_coverage_quote": "No existing insurance",
    "coverage_status": "none",
    "new_customer_quote": "",
    "question_focus": "general",
    "focus_quote": "",
    "missing_details": []
  },
  "lead_active": true,
  "lead_draft": {
    "product_id": "cheeva",
    "product_quote": "Khum Cheeva",
    "name": {
      "value": "Demo Alex",
      "quote": "My name is Demo Alex"
    },
    "occupation": {
      "value": "student",
      "quote": "I am a student"
    },
    "income": {
      "value": "20,000 THB per month",
      "quote": "My income is 20,000 THB per month"
    }
  }
}
```

## 9. Factual interruption preserves draft

Session: `demo-a`

Result: PASS

Customer:

For Khum Cheeva, how many years do I pay the base-policy premiums?

Assistant (verbatim):

For the Khum Cheeva (คุ้มชีวา) plan, the base-policy premiums are paid over a period of 10 years.

Sources:
[1] 02_SCB-InsureX_Khum-Cheeva_90-10_180669.pdf, page 1
[3] 02_SCB-InsureX_Khum-Cheeva_90-10_180669.pdf, page 3

Executed nodes: `rewrite → collect_lead → retrieve → answer`

## 10. Invalid phone does not save

Session: `demo-a`

Result: PASS

Customer:

My contact number is 123.

Assistant (verbatim):

Please check your contact number and resend it (8–15 digits).

Executed nodes: `rewrite → collect_lead`

## 11. Incomplete lead is absent from SQLite

Session: `demo-a`

Result: PASS

Observed saved data:

```json
[]
```

## 12. Complete lead is saved

Session: `demo-a`

Result: PASS

Customer:

My contact number is 0800000000.

Assistant (verbatim):

Your lead details have been saved to the local database. This records your interest; it is not an insurance application or confirmation of coverage.

Executed nodes: `rewrite → collect_lead`

## 13. Structured SQLite record matches customer

Session: `demo-a`

Result: PASS

Observed saved data:

```json
[
  {
    "lead_id": "b85dcda5-2645-5c07-b82f-d27c7410cbc1",
    "session_id": "demo-a",
    "product_id": "cheeva",
    "name": "Demo Alex",
    "occupation": "student",
    "income": "20,000 THB per month",
    "contact_number": "0800000000",
    "evidence": {
      "name": "My name is Demo Alex",
      "occupation": "I am a student",
      "income": "My income is 20,000 THB per month",
      "contact_number": "My contact number is 0800000000",
      "product": "Khum Cheeva"
    }
  }
]
```

## 14. Customer B remains independent

Session: `demo-b`

Result: PASS

Customer:

What age, annual budget and protection goal have I told you?

Assistant (verbatim):

From what you told me:

- Age: I am age 45
- Premium budget: Annual insurance budget 60000 THB
- Latest goal: I want help paying hospital bills

Executed nodes: `rewrite → recommend`

## 15. Thai product interest

Session: `demo-thai`

Result: PASS

Customer:

สนใจคุ้มออมสุขค่ะ

Assistant (verbatim):

เข้าสู่โหมดเก็บข้อมูลผู้สนใจ กรุณาระบุ ชื่อ, อาชีพ, รายได้ พร้อมสกุลเงินและระบุรายเดือนหรือรายปี, เบอร์ติดต่อ เพื่อบันทึกในฐานข้อมูลภายใน พิมพ์ /cancel-lead เพื่อยกเลิก

Executed nodes: `rewrite → collect_lead`

## 16. Thai structured lead

Session: `demo-thai`

Result: PASS

Customer:

ชื่อ เดโมบี อาชีพ ครู รายได้ 30000 บาทต่อเดือน เบอร์ติดต่อ 0811111111

Assistant (verbatim):

บันทึกข้อมูลผู้สนใจในฐานข้อมูลภายในแล้ว การบันทึกนี้ไม่ใช่การสมัครหรือยืนยันรับประกันภัย

Executed nodes: `rewrite → collect_lead`

## 17. Thai record is separate

Session: `demo-thai`

Result: PASS

Observed saved data:

```json
[
  {
    "lead_id": "76f832e1-9e0b-5b52-8d48-82e07f1fc9e8",
    "session_id": "demo-thai",
    "product_id": "aomsook",
    "name": "เดโมบี",
    "occupation": "ครู",
    "income": "30000 บาทต่อเดือน",
    "contact_number": "0811111111",
    "evidence": {
      "name": "ชื่อ เดโมบี",
      "occupation": "อาชีพ ครู",
      "income": "รายได้ 30000 บาทต่อเดือน",
      "contact_number": "เบอร์ติดต่อ 0811111111",
      "product": "คุ้มออมสุข"
    }
  }
]
```

## 18. Start incomplete lead

Session: `demo-cancel`

Result: PASS

Customer:

I am interested in Khum Talodcheep CI Plus.

Assistant (verbatim):

Lead collection: please provide your name, occupation, income amount (and currency/monthly or yearly frequency), contact number. These details will be saved to the local database when complete. Type /cancel-lead to cancel.

Executed nodes: `rewrite → collect_lead`

## 19. Cancel without saving

Session: `demo-cancel`

Result: PASS

Customer:

/cancel-lead

Assistant (verbatim):

Lead collection cancelled. Incomplete details were not saved.

Executed nodes: `rewrite → collect_lead`

## 20. Cancelled lead is absent from SQLite

Session: `demo-cancel`

Result: PASS

Observed saved data:

```json
[]
```

## 21. Detailed critical illness comparison

Session: `demo-rag`

Result: PASS

Customer:

What is the difference between the critical illness protection in Khum Cheeva and Khum Talodcheep CI Plus?

Assistant (verbatim):

The critical illness protection in Khum Cheeva and Khum Talodcheep CI Plus differ primarily in coverage scope and benefit structure. Khum Cheeva (90/10) offers critical illness protection through an optional rider called CI 50, which is named as such but does not explicitly define or confirm coverage of 50 illnesses; the exact illnesses covered are not detailed in the brochure. The CI 50 rider provides staged benefits for early and severe stages of critical illnesses, with example sums insured and payouts illustrated for a male age 40, but the rider premium payment duration and full illness definitions are not specified. Khum Cheeva requires attaching eligible riders such as accident, CI 50, or cancer riders, with minimum sums insured depending on the base policy amount, but CI 50 is only one selectable option, not automatically included.

In contrast, Khum Talodcheep CI Plus integrates life and critical illness coverage in one product, covering 15 specified severe critical illnesses and 4 specified early-stage illnesses. It pays 25% of the sum insured upon diagnosis of one of the 4 early-stage illnesses, waives further premiums, and continues coverage. For the 15 severe illnesses, it pays 100% of the sum insured or the total premiums paid (excluding riders), whichever is greater, minus any early-stage benefits already paid. The policy terminates after a full severe illness payout. It also has a 90-day waiting period for critical illness coverage and specific exclusions. The premium payment terms can be 5, 10, or 20 years, with coverage up to age 90.

In summary, Khum Cheeva's critical illness protection is via a rider with unspecified illness definitions and staged payouts, while Khum Talodcheep CI Plus offers defined coverage for a set list of early and severe critical illnesses with premium waiver and policy termination conditions after full payout. The CI Plus product provides more detailed illness coverage and benefit structure in the brochure, whereas Khum Cheeva's CI 50 rider details are limited and not automatically included with the base policy.

Sources:
[2] 02_SCB-InsureX_Khum-Cheeva_90-10_180669.pdf, page 2
[3] 02_SCB-InsureX_Khum-Cheeva_90-10_180669.pdf, page 3
[4] 11_SCB-InsureX_Khum-Talodcheep-CI-Plus_90-5_90-10_90-20_180669.pdf, page 1
[5] 11_SCB-InsureX_Khum-Talodcheep-CI-Plus_90-5_90-10_90-20_180669.pdf, page 2
[6] 11_SCB-InsureX_Khum-Talodcheep-CI-Plus_90-5_90-10_90-20_180669.pdf, page 3

Executed nodes: `rewrite → retrieve → answer`

## 22. Health rider dependency

Session: `demo-rag`

Result: PASS

Customer:

Does Khum Raksa Maojai Extra need an eligible base life policy?

Assistant (verbatim):

Yes, Khum Raksa Maojai Extra is a health insurance rider that requires attachment to a base life insurance policy. This is indicated by the description that it is a "สัญญาเพิ่มเติมการประกันภัยสุขภาพ" (health insurance rider) and the coverage duration is tied to the base life policy's coverage term or until age 99, whichever is earlier. Therefore, it cannot be purchased as a standalone product without a base life insurance policy.

Sources:
[4] 07_SCB-InsureX_Khum-Raksa-Maojai-Extra_180669.pdf, page 4

Executed nodes: `rewrite → retrieve → answer`

## 23. Savings coverage and payment separation

Session: `demo-rag`

Result: PASS

Customer:

For Khum Aomsook 25/15, what are the coverage and premium-payment periods?

Assistant (verbatim):

Verified plan terms:

1. Khum Aomsook / คุ้มออมสุข (25/15): Savings insurance. Coverage: 25 years. Premium payments: 15 years, depending on the variant. [1]


Sources:

[1] 09_SCB-InsureX_Khum-Aomsook_25-15_180669.pdf, pages 1, 2

Executed nodes: `rewrite → catalog_answer`

## 24. Pension duration uses entry age

Session: `demo-rag`

Result: PASS

Customer:

For Khum Bamnan 85/55, does everyone pay premiums for exactly 10 years?

Assistant (verbatim):

No, not everyone pays premiums for exactly 10 years under Khum Bamnan 85/55. The premium payment period depends on the insured's age at entry and the chosen plan. For example, the 85/55 plan requires premium payments until age 55, which may or may not be exactly 10 years depending on the insured's current age. The example of a male aged 45 paying premiums until age 55 results in a 10-year payment period, but this is specific to that example. Therefore, the premium payment duration varies and is not universally fixed at 10 years for all policyholders.

Sources:
[1] 05_SCB-InsureX_Khum-Bamnan_85-55_85-60_85-65_180669.pdf, page 1
[2] 05_SCB-InsureX_Khum-Bamnan_85-55_85-60_85-65_180669.pdf, page 2
[3] 05_SCB-InsureX_Khum-Bamnan_85-55_85-60_85-65_180669.pdf, page 3
[4] 05_SCB-InsureX_Khum-Bamnan_85-55_85-60_85-65_180669.pdf, page 4

Executed nodes: `rewrite → retrieve → answer`

Checker review: Accepted the valid phrase "age at entry" after source review. Actual answer unchanged; original strict-checker result is preserved.

## 25. Missing product evidence

Session: `demo-unknown`

Result: PASS

Customer:

What does the nonexistent product Demo Unicorn 123 cover?

Assistant (verbatim):

The provided documents do not contain any information about a product named Demo Unicorn 123. Therefore, I cannot provide details about its coverage.

Executed nodes: `rewrite → retrieve → answer`

## 26. Saved session IDs are separate

Session: `all`

Result: PASS

Observed saved data:

```json
[
  "demo-a",
  "demo-b",
  "demo-cancel",
  "demo-catalog",
  "demo-rag",
  "demo-thai",
  "demo-unknown"
]
```
