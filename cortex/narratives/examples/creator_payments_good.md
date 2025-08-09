_# Narrative: PF.BI.V_CREATOR_PAYMENTS_UNION (Good Example)

- View/Table: PF.BI.V_CREATOR_PAYMENTS_UNION (domain: creator_payments)
- Purpose: Unified analytics view for creator payments sourced from Stripe invoices and transfers. Used to filter, aggregate, and rank payments by status, date, amount, company, campaign, and creator.

## Business rules
- Allowed operations: SELECT, WHERE, GROUP BY, ORDER BY, LIMIT
- Always include LIMIT (default 1000)
- No joins, subqueries, or CTEs; single-table queries only
- Timezone: UTC; Dates are TIMESTAMP_NTZ
- If no date filter provided, prefer last 365 days
- When both exist, prefer filtering by PAYMENT_DATE over CREATED_DATE
- Canonical PAYMENT_STATUS values: paid, pending, open, failed
- Case-insensitive matching for names; numeric comparisons for amounts
- Safe sorts: by PAYMENT_DATE DESC, PAYMENT_AMOUNT DESC, CREATOR_NAME ASC

## Key columns
- PAYMENT_STATUS
  - Meaning: State of the payment lifecycle
  - Synonyms: status, state
  - Examples: paid, pending, open, failed
  - Relationships: If REFERENCE_TYPE='Invoice', maps to STRIPE.INVOICES.STATUS
- PAYMENT_AMOUNT
  - Meaning: Amount in USD
  - Synonyms: amount, value, dollars, $
  - Examples: 52.80, 103.72, 275.00, 500.00
  - Relationships: Derived from Stripe invoices/charges
- PAYMENT_DATE
  - Meaning: When the payment was made (UTC)
  - Synonyms: date, paid on, posted on, after/before/between
  - Examples: 2024-08-01, 2024-09-15
  - Relationships: Prefer this over CREATED_DATE for recency
- CREATED_DATE
  - Meaning: Record creation timestamp (UTC)
  - Synonyms: created, ingested, inserted
  - Examples: 2024-08-02T13:45:00Z
- PAYMENT_TYPE
  - Meaning: Payment route/category
  - Synonyms: type, channel, method
  - Examples: Direct Mode, Transfer, Invoice
- REFERENCE_TYPE
  - Meaning: Upstream object type
  - Synonyms: source type
  - Examples: Invoice, Transfer
- REFERENCE_ID
  - Meaning: Upstream object identifier
  - Synonyms: source id, invoice id, transfer id
  - Examples: in_1RFJL..., tr_123...
- CREATOR_NAME
  - Meaning: Display name of the creator payee
  - Synonyms: creator, influencer, talent
  - Examples: "Sara Tewksbury", "Rees Gibbons"
- COMPANY_NAME
  - Meaning: Paying company/customer
  - Synonyms: brand, customer
  - Examples: "Realand Nutrition", "Dominion Supplements"
- CAMPAIGN_NAME
  - Meaning: Campaign associated with the payment
  - Synonyms: campaign, program
  - Examples: "Summer Cocktail Series…", "Calling All Photographers…"

## Typical questions
- Show paid payments over $100 since last month by campaign
- Top 10 creators by total payment amount this quarter
- Pending invoices by company for the past 90 days
- Total paid and pending sums per company YTD
- All payments for "Realand Nutrition" last 30 days
- Creators with payments > $500 in the last 60 days

## Sensitive data
- Do not surface emails, addresses, bank/account numbers, or internal IDs beyond REFERENCE_ID and Stripe IDs already exposed in this view.

## Defaults
- LIMIT 1000
- ORDER BY PAYMENT_DATE DESC
- Time window fallback: last 365 days if not specified
- Currency: USD; Timezone: UTC
_