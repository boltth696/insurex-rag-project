# Offline submission demo log

Recorded: 2026-10-04T09:27:42.637229+07:00

Actual application output using synthetic customers and temporary SQLite databases.

Checks: 5/5.

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

## 3. Offline second session

Session: `demo-b`

Result: PASS

Customer:

How many years do I pay premiums for Khum Cheeva?

Assistant (verbatim):

Verified plan terms:

1. Khum Cheeva / คุ้มชีวา (90/10): Life insurance with additional rider options. Coverage: until age 90. Premium payments: 10 years, depending on the variant. [1]


Sources:

[1] 02_SCB-InsureX_Khum-Cheeva_90-10_180669.pdf, pages 1, 3

Executed nodes: `rewrite → catalog_answer`

## 4. Offline history restored

Session: `demo-catalog`

Result: PASS

Observed saved data:

```json
{
  "history": [
    [
      "user",
      "What products are available?"
    ],
    [
      "assistant",
      "The supplied brochures describe these 5 product families:\n\n1. Khum Cheeva / คุ้มชีวา (90/10): Life insurance with additional rider options. Coverage: until age 90. Premium payments: 10 years, depending on the variant. [1]\n\n2. Khum Bamnan / คุ้มบำนาญ (85/55, 85/60, 85/65): Pension insurance. Coverage: until age 85. Premium payments: 85/55: until age 55; 85/60: until age 60; 85/65: until age 65. [2]\n\n3. Khum Raksa Maojai Extra / คุ้มรักษา เหมาจ่าย เอ็กซ์ตร้า (Extra): Health insurance rider; benefits depend on the selected plan. Coverage: until age 99, or the base life policy's coverage term if shorter, subject to conditions. The brochure does not specify a fixed number of premium-payment years. [3]\n\n4. Khum Aomsook / คุ้มออมสุข (25/15): Savings insurance. Coverage: 25 years. Premium payments: 15 years, depending on the variant. [4]\n\n5. Khum Talodcheep CI Plus / คุ้มตลอดชีพ ซีไอ พลัส (90/5, 90/10, 90/20): Life and critical illness insurance. Coverage: until age 90. Premium payments: 5, 10, 20 years, depending on the variant. [5]\n\n\nSources:\n\n[1] 02_SCB-InsureX_Khum-Cheeva_90-10_180669.pdf, pages 1, 3\n\n[2] 05_SCB-InsureX_Khum-Bamnan_85-55_85-60_85-65_180669.pdf, pages 1, 4\n\n[3] 07_SCB-InsureX_Khum-Raksa-Maojai-Extra_180669.pdf, pages 1, 4\n\n[4] 09_SCB-InsureX_Khum-Aomsook_25-15_180669.pdf, pages 1, 2\n\n[5] 11_SCB-InsureX_Khum-Talodcheep-CI-Plus_90-5_90-10_90-20_180669.pdf, pages 1, 3"
    ],
    [
      "user",
      "Which product has the shortest premium-payment period?"
    ],
    [
      "assistant",
      "The shortest fixed premium-payment option is คุ้มตลอดชีพ ซีไอ พลัส 90/5: 5 years.\n\nThe supplied brochures describe these 5 product families:\n\n1. Khum Cheeva / คุ้มชีวา (90/10): Life insurance with additional rider options. Coverage: until age 90. Premium payments: 10 years, depending on the variant. [1]\n\n2. Khum Bamnan / คุ้มบำนาญ (85/55, 85/60, 85/65): Pension insurance. Coverage: until age 85. Premium payments: 85/55: until age 55; 85/60: until age 60; 85/65: until age 65. [2]\n\n3. Khum Raksa Maojai Extra / คุ้มรักษา เหมาจ่าย เอ็กซ์ตร้า (Extra): Health insurance rider; benefits depend on the selected plan. Coverage: until age 99, or the base life policy's coverage term if shorter, subject to conditions. The brochure does not specify a fixed number of premium-payment years. [3]\n\n4. Khum Aomsook / คุ้มออมสุข (25/15): Savings insurance. Coverage: 25 years. Premium payments: 15 years, depending on the variant. [4]\n\n5. Khum Talodcheep CI Plus / คุ้มตลอดชีพ ซีไอ พลัส (90/5, 90/10, 90/20): Life and critical illness insurance. Coverage: until age 90. Premium payments: 5, 10, 20 years, depending on the variant. [5]\n\n\nSources:\n\n[1] 02_SCB-InsureX_Khum-Cheeva_90-10_180669.pdf, pages 1, 3\n\n[2] 05_SCB-InsureX_Khum-Bamnan_85-55_85-60_85-65_180669.pdf, pages 1, 4\n\n[3] 07_SCB-InsureX_Khum-Raksa-Maojai-Extra_180669.pdf, pages 1, 4\n\n[4] 09_SCB-InsureX_Khum-Aomsook_25-15_180669.pdf, pages 1, 2\n\n[5] 11_SCB-InsureX_Khum-Talodcheep-CI-Plus_90-5_90-10_90-20_180669.pdf, pages 1, 3\n\nThis ranks fixed payment-year options only. Pension payment durations depend on your entry age; the health rider has no stated fixed payment-year period. These are not ranked as fixed-year plans."
    ]
  ],
  "profile": {},
  "lead_active": false,
  "lead_draft": {}
}
```

## 5. Saved session IDs are separate

Session: `all`

Result: PASS

Observed saved data:

```json
[
  "demo-b",
  "demo-catalog"
]
```
