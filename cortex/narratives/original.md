# Narrative: PF.BI.V_CREATOR_PAYMENTS_UNION

- View/Table: PF.BI.V_CREATOR_PAYMENTS_UNION (domain: creator_payments)
- Purpose: Unified analytics view for creator payments sourced from Stripe invoices and transfers. Used to filter, aggregate, and rank payments by status, date, amount, company, campaign, and creator.

## Business rules
- Allowed operations: SELECT, WHERE, GROUP BY, ORDER BY, LIMIT
- Always include LIMIT (default 1000)
- No joins, subqueries, or CTEs; single-table queries only
- Timezone: UTC; Date types: TIMESTAMP_NTZ
- Default time window if none provided: last 365 days
- Preferred date column for recency: PAYMENT_DATE over CREATED_DATE
- Canonical PAYMENT_STATUS values: paid, pending, open, failed
- Safe sorts: PAYMENT_DATE DESC, PAYMENT_AMOUNT DESC, CREATOR_NAME ASC
- Forbidden: Updates, deletes, DDL, unions, joins, CTEs

## Key columns
- PAYMENT_STATUS
  - Meaning: State of the payment lifecycle
  - Synonyms: status, state
  - Examples: paid, pending, open, failed
  - Relationships: If REFERENCE_TYPE='Invoice', maps to STRIPE.INVOICES.STATUS
- PAYMENT_AMOUNT
  - Meaning: Amount in USD
  - Synonyms: amount, value, dollars, $
  - Examples: 26.16, 52.80, 88.00, 165.00, 207.14, 495.00
  - Relationships: Derived from Stripe invoices/charges
- PAYMENT_DATE
  - Meaning: When the payment was made (UTC)
  - Synonyms: date, paid on, posted on, after/before/between
  - Examples: recent dates from the dataset
  - Relationships: Prefer over CREATED_DATE for recency
- CREATED_DATE
  - Meaning: Record creation timestamp (UTC)
  - Synonyms: created, ingested, inserted
  - Examples: recent timestamps
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
  - Examples: in_1REYjj..., in_1RrQUU..., in_1ReiGM...
- CREATOR_NAME
  - Meaning: Display name of the creator payee
  - Synonyms: creator, influencer, talent
  - Examples: "Katie Reardon", "Milan & Romana Outfluencers", "Jess Cohen"
- COMPANY_NAME
  - Meaning: Paying company/customer
  - Synonyms: brand, customer
  - Examples: "Ambrook", "Popfly Inc", "ROLL Recovery"
- CAMPAIGN_NAME
  - Meaning: Campaign associated with the payment
  - Synonyms: campaign, program
  - Examples: "PAID UGC Campaign - Recovery Tools For Athletes", "Help Us Grow Realand — Try It Free & Share Your Thoughts"
- STRIPE_CUSTOMER_ID
  - Meaning: Stripe customer identifier
  - Synonyms: customer id
  - Examples: cus_S2sUi2..., cus_RO2Pqf..., cus_Ry42jV...
- STRIPE_CUSTOMER_NAME
  - Meaning: Stripe customer display name
  - Synonyms: customer name
  - Examples: "Ambrook", "Popfly Inc", "ROLL Recovery"
- STRIPE_CONNECTED_ACCOUNT_ID
  - Meaning: Stripe connected account identifier
  - Synonyms: connected account id
  - Examples: acct_1RDpsK..., acct_1QpjBI..., acct_1RGmSx...
- STRIPE_CONNECTED_ACCOUNT_NAME
  - Meaning: Stripe connected account display name
  - Synonyms: connected account name
  - Examples: "Reardon Land and Cattle LLC", "Uproot and Adventure", "Jessica Cohen"
- USER_ID
  - Meaning: Popfly user identifier associated to the creator
  - Synonyms: user id
  - Examples: 8789, 8157, 8859

## Typical questions
- Show paid payments over $100 since last month by campaign
- Top 10 creators by total payment amount this quarter
- Pending invoices by company for the past 90 days
- Total paid and pending sums per company YTD
- All payments for a specific brand (e.g., "Realand Nutrition") last 30 days
- Creators with payments > $500 in the last 60 days

## Sensitive data
- Do not surface emails, addresses, bank/account numbers, or internal IDs beyond REFERENCE_ID and Stripe IDs already exposed in this view.

## Defaults
- LIMIT 1000
- ORDER BY PAYMENT_DATE DESC
- Time window fallback: last 365 days
- Currency: USD; Timezone: UTC
