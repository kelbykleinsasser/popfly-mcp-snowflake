# Narrative: PF.BI.MV_CREATOR_PAYMENTS_UNION

- View/Table: PF.BI.MV_CREATOR_PAYMENTS_UNION (domain: creator_payments, creator_invoices)
- Purpose: Unified view for Creator payments (AKA invoice payment, transfer, balance transfer, payment) and Invoices (AKA creator invoice, creator bill, bill) using data sourced primarily from Stripe (PF.BI.S_*), but also with extensive joins to Popfly metadata (PF.BI.PF_*, PF.BI.MV_*, PF.BI.CP_*)


## Business rules
- Allowed operations: SELECT, WHERE, GROUP BY, ORDER BY, LIMIT
- **CRITICAL: NO JOINS ALLOWED. Query ONLY from PF.BI.MV_CREATOR_PAYMENTS_UNION table. All data must come from this single table.**
- Never join to other tables or views. All required data is already in MV_CREATOR_PAYMENTS_UNION
- Forbidden: Updates, deletes, DDL, JOINs of any kind (INNER, LEFT, RIGHT, FULL, CROSS), UNION, WITH clauses
- Timezone: UTC; Date types: TIMESTAMP_NTZ
- Default time window if none provided: January 2025 and later
- Preferred date column for recency: PAYMENT_DATE over CREATED_DATE
- Canonical PAYMENT_STATUS values: paid, pending, open, failed
- Canonical PAYMENT_TYPE values: Agency Mode, Direct Mode, Unassigned

## SQL Generation Rules for PAYMENT_TYPE
**CRITICAL: When generating SQL WHERE clauses for PAYMENT_TYPE:**
- If user mentions "labs", "Popfly Labs", "agency services", or "agency" → Generate: `WHERE PAYMENT_TYPE = 'Agency Mode'`
- If user mentions "self-serve", "self serve", "platform", or "direct" → Generate: `WHERE PAYMENT_TYPE = 'Direct Mode'`
- NEVER use the literal values "Labs", "labs", "Popfly Labs", "self-serve", etc. in SQL
- The PAYMENT_TYPE column ONLY contains: 'Agency Mode', 'Direct Mode', 'Unassigned'
- Example: User says "show labs payments" → SQL must be: `SELECT * FROM MV_CREATOR_PAYMENTS_UNION WHERE PAYMENT_TYPE = 'Agency Mode'`

**ABSOLUTELY CRITICAL - NEVER TREAT AS COMPANY NAMES:**
The following terms (case-insensitive) MUST ALWAYS be interpreted as PAYMENT_TYPE values, NEVER as COMPANY_NAME or STRIPE_CUSTOMER_NAME:
- "labs", "Labs", "LABS" → ALWAYS means `PAYMENT_TYPE = 'Agency Mode'`
- "popfly labs", "Popfly Labs", "POPFLY LABS" → ALWAYS means `PAYMENT_TYPE = 'Agency Mode'`
- "agency", "Agency", "AGENCY" → ALWAYS means `PAYMENT_TYPE = 'Agency Mode'`
- "agency services", "Agency Services" → ALWAYS means `PAYMENT_TYPE = 'Agency Mode'`
- "agency mode", "Agency Mode" → ALWAYS means `PAYMENT_TYPE = 'Agency Mode'`
- "self-serve", "self serve", "selfserve" → ALWAYS means `PAYMENT_TYPE = 'Direct Mode'`
- "platform", "Platform" → ALWAYS means `PAYMENT_TYPE = 'Direct Mode'`
- "direct", "Direct" → ALWAYS means `PAYMENT_TYPE = 'Direct Mode'`
- "direct mode", "Direct Mode" → ALWAYS means `PAYMENT_TYPE = 'Direct Mode'`

**NEVER generate SQL like:**
- ❌ `WHERE COMPANY_NAME = 'Popfly Labs'` 
- ❌ `WHERE COMPANY_NAME = 'Agency Services'`
- ❌ `WHERE STRIPE_CUSTOMER_NAME = 'Labs'`
- ❌ `WHERE COMPANY_NAME = 'Platform'`

**ALWAYS generate SQL like:**
- ✅ `WHERE PAYMENT_TYPE = 'Agency Mode'` (for labs/agency terms)
- ✅ `WHERE PAYMENT_TYPE = 'Direct Mode'` (for self-serve/platform terms)
- Safe sorts: PAYMENT_DATE DESC, PAYMENT_AMOUNT DESC, CREATOR_NAME ASC
- Note: View contains both invoices (creator bills) and transfers (payments to creators)
- PAYMENT_TYPE carries considerable weight in this context. The PAYMENT_TYPE column contains the designations Agency Mode, Direct Mode, and Unassigned. Agency Mode represents Popfly  agency services (Popfly Labs, labs, agency) where we source and pay creators, and later invoice customers once campaigns (projects) have been completed; Direct Mode represents direct customer-creator relationships where Popfly is merely providing the platform upon which transactions take place. Creators "apply" to Campaigns and once accepted can create and submit content, interact with the Customer users on the platform, submit invoices, and get paid.
- PAYMENT_TYPE = "Unassigned" are not to be ignored. They are a catch all for invoices that don't fit neatly into Agency Mode or Direct Mode. These records should be transient as occassional data hygeine processes add necessary categorization data to move them to either Direct Mode or Agency Mode. For the most persistent records in this category they a likely Popfly Inc as Customer which commonly represent deals done with creators to produce marketing content for Popfly directly. In other words, we are the customer and as such the records legitimately do not fit into either of the other buckets. The remainder of the records in this category are only useful when PAYMENT_STATUS='paid' and REFERENCE_TYPE contains 'transfer'. This will show unassigned payments made to creators for unknown reasons, but should appear in inquiries such as "show me all of the payments made to Jordan Kahana". 
- Reasonably good Creator Invoice and Transfer data management began taking place starting around January 1, 2025. Never return Invoice or Transfer data from before this period.
- The term Customer can mean more than one thing on our platform. First, in Agency Mode, the Customer is Popfly's Customer because they're paying us to perform a service for them. In the case of Direct Mode, a Customer is both a subscriber to Popfly (they pay us a monthly fee to access Creators and use our platform) and a Customer is also the Customer to the Creator who is performing the services and will invoice the Customer directly.
- PF.BI.MV_CREATOR_PAYMENTS_UNION uses PF.BI.V_LOOKUP_AGENCYMODECLIENTIDS to separate Customers into Direct Mode and Agency Mode whereby if the STRIPE_CUSTOMER_ID appears in PF.BI.V_LOOKUP_AGENCYMODECLIENTIDS they are designated as for Agency Mode Customers. If not, they are designated as Direct Mode Customers. 
- Not all Invoices are connected to Campaigns (AKA projects). Some Invoices are issued by creators without a reference to a Campaign. These can be identified by REFERENCE_TYPE = "Invoice (No Campaign)". This is problematic to the degree that Agency Mode clients like to receive Popfly Invoices that show each Creator along with the Campaign the Creator fee is intended to cover. This is for their internal budgeting purposes so they can more easily distinguish the marketing ROI.
- It's quite common for Creators to issue multiple Invoices for the same project for not other reason than that they think that it will get them paid more quickly, or they believe that somehow either we or their Direct Mode customer forgot to pay them. Sometimes duplicate Invoices are issued with one showing REFERENCE_TYPE = "Invoice (No Campaign)" and the other REFERENCE_TYPE = "Invoice" (which is connected to a Campaign). The reality is that they have almost no other recourse and as such it's understandable when they take the only action that they can take, but this leads to corrupt--or at minimum, unclear--data.
- Creators can be identified in this dataset by--most commonly--CREATOR_NAME and STRIPE_CONNECTED_ACCOUNT_NAME. It's possible that users may also want to find Creators by STRIPE_CONNECTED_ACCOUNT_ID or even USER_ID from time to time.
- REFERENCE_ID means two different things depending upon the value in REFERENCE_TYPE. When REFERENCE_TYPE contains "Transfer", REFERENCE_ID points to a Transfer ID (PF.BI.S_TRANSFERS.ID). When REFERENCE_TYPE contains "Invoice", REFERENCE_ID points to an Invoice ID (PF.BI.S_INVOICES.ID).
- CREATED_DATE represents two different things depending upon REFERENCE_TYPE. When REFERENCE_TYPE contains "Transfer", the CREATED_DATE represents the date that funds were transferred from either Popfly (our company) or a Customer (in rare cases), representing a Creator Payment. When REFERENCE_TYPE contains "Invoice" CREATED_DATE represents the date that the Creator issued the Invoice. Unfortunately this date is not entirely useful because there are no standards in place as to when Creator's decide to submit invoices for their work. Some Creators will issues Invoices at the moment they are accepted to a Campaign--long before they have actually completed their work--and as such it renders the due data meaningless. 
- As of August 1st, 2025 we are underway with a project that will simplify the process of identifying Invoices that are actually due for payment. These "approvals" will be issued by Account Managers and stored in a table called PF.BI.CP_PAYMENT_APPROVALS. If the user mentions anything about "approval", they are most likely talking about data in this table, which again at the moment is sparse and should not carry much weight in the inquiry process as of yet. 
- PAYMENT_DATE is the actual date that payment occured either through a Transfer or Invoice Payment. PAYMENT_DATE is always null when an invoice has not yet been paid. When a user asks to see Creator Payments, they are referring to actual payments where PAYMENT_DATE is not null. When a user asks to see Creator Invoices, they are asking for Invoices where PAYMENT_STATUS contains "paid", "open", "unpaid".
- Companies (AKA company, client, customer, brand) can be identified by COMPANY_NAME, and STRIPE_CUSTOMER_NAME. Less commonly, users may want to look up Invoices and Transfers by CAMPAIGN_NAME (sometimes CAMPAIGN_NAME contains the name of the company), or even less commonly by STRIPE_CUSTOMER_ID.
- PAYMENT_AMOUNT is always the Invoice amount when PAYMENT_STATUS<>'paid'. In these cases these should not be referred to as payments as they are only invoices. When PAYMENT_STATUS='paid' the amount is either the Invoice amount (PAYMENT_TYPE="Direct Mode") or Transfer amount (PAYMENT_TYPE="Agency Mode")
- CREATOR_NAME can be null sometimes. When it is, use STRIPE_CONNECTED_ACCOUNT_NAME in its place. Essentially a coalesce statement that prioritizes CREATOR_NAME first


## CRITICAL SQL GENERATION RULES FOR COUNTING AND AGGREGATION
**IMPORTANT: ONLY THESE COLUMNS EXIST IN MV_CREATOR_PAYMENTS_UNION:**
1. PAYMENT_TYPE
2. REFERENCE_ID (use this as the unique identifier)
3. REFERENCE_TYPE
4. STRIPE_CONNECTED_ACCOUNT_ID
5. STRIPE_CUSTOMER_ID
6. USER_ID
7. CREATOR_NAME
8. STRIPE_CONNECTED_ACCOUNT_NAME
9. STRIPE_CUSTOMER_NAME
10. COMPANY_NAME
11. CAMPAIGN_NAME
12. PAYMENT_STATUS
13. PAYMENT_AMOUNT
14. PAYMENT_DATE
15. CREATED_DATE

**THESE COLUMNS DO NOT EXIST - NEVER USE THEM:**
- ❌ PAYMENT_ID (does not exist - use REFERENCE_ID instead)
- ❌ ID (does not exist)
- ❌ INVOICE_ID (does not exist - use REFERENCE_ID)
- ❌ TRANSFER_ID (does not exist - use REFERENCE_ID)
- ❌ PAYMENT_DATETIME (does not exist - use PAYMENT_DATE)

**FOR COUNTING AND AGGREGATION:**
- To count payments: Use `COUNT(*)` or `COUNT(REFERENCE_ID)`
- To count distinct payments: Use `COUNT(DISTINCT REFERENCE_ID)`
- To sum amounts: Use `SUM(PAYMENT_AMOUNT)`
- To count by type: Use `COUNT(*)` with `GROUP BY PAYMENT_TYPE`
- NEVER use `COUNT(PAYMENT_ID)` - this column does not exist

## CRITICAL: Exact Company Name Matching Rules
**IMPORTANT: When users specify company names, use EXACT matching to avoid substring matches:**

When a user asks for a specific company by name (e.g., "PAKA"), you MUST use exact matching:
- ✅ CORRECT: `WHERE COMPANY_NAME = 'PAKA'` (exact match)
- ✅ CORRECT: `WHERE STRIPE_CUSTOMER_NAME = 'PAKA'` (exact match)
- ❌ WRONG: `WHERE COMPANY_NAME LIKE '%PAKA%'` (would incorrectly match "ALPAKA")

**Known company names that require exact matching:**
- PAKA (not ALPAKA)
- ALPAKA (not PAKA)

**When to use LIKE patterns:**
- Only when the user explicitly asks for partial matches (e.g., "companies containing 'tech'")
- When searching for campaigns or creators where partial matching makes sense
- Never for known company names unless specifically requested

**Examples:**
- "PAKA payments" → `WHERE COMPANY_NAME = 'PAKA'`
- "companies like PAKA" → `WHERE COMPANY_NAME LIKE '%PAKA%'`
- "show me PAKA creator payment totals" → `WHERE COMPANY_NAME = 'PAKA'`

## Key columns
- PAYMENT_STATUS
  - Meaning: State of the payment lifecycle, always "paid" when REFERENCE_TYPE contains "Transfer".
  - Synonyms: status, state, invoice status, payment status, transfer status, creator payment status, creator invoice status
  - Examples: paid, open
  - Relationships: When REFERENCE_TYPE='Invoice' and PAYMENT_TYPE='Direct Mode', always maps to PF.BI.S_INVOICES.STATUS via REFERENCE_ID = PF.BI.S_INVOICES.ID. When REFERENCE_TYPE contains 'Transfer', always maps to PF.BI.S_TRANSFERS via REFERENCE_ID = PF.BI.S_TRANSFERS.ID.
- PAYMENT_AMOUNT
  - Meaning: Amount paid to creator in USD 
  - Synonyms: amount, value, invoice amount when PAYMENT_STATUS is no
  - Examples: 26.16, 52.80, 88.00, 165.00, 207.14, 495.00
- PAYMENT_DATE
  - Meaning: When the payment was made (UTC), only applied when PAYMENT_STATUS = 'paid'
  - Synonyms: invoice date, transfer date, payment date, date, date paid, paid on, posted on
  - Examples: recent dates from the dataset
- CREATED_DATE
  - Meaning: Invoice or Transfer (payment) record creation timestamp (UTC), applies regardless of PAYMENT_STATUS
  - Synonyms: date, created, issued, transfer date, invoice date, billing date, paid date, payment date
  - Examples: recent timestamps
- PAYMENT_TYPE
  - Meaning: Business model classification. ONLY contains 'Agency Mode', 'Direct Mode', or 'Unassigned'. When users say "labs" they mean 'Agency Mode'. When users say "self-serve" or "platform" they mean 'Direct Mode'.
  - Synonyms: labs (means Agency Mode), Popfly Labs (means Agency Mode), agency (means Agency Mode), self-serve (means Direct Mode), platform (means Direct Mode), business model
  - Examples: Agency Mode, Direct Mode, Unassigned
  - Relationships: "labs" always translates to PAYMENT_TYPE='Agency Mode', never COMPANY_NAME='Labs'
- REFERENCE_TYPE
  - Meaning: Upstream object type
  - Synonyms: source type
  - Examples: Invoice, Transfer
- REFERENCE_ID
  - Meaning: Upstream object identifier, either a stripe invoice id or a stripe transfer id
  - Synonyms: source id, invoice id, transfer id
  - Examples: in_1REYjj..., in_1RrQUU..., tr_1ReiGM...
  - Relationships: When REFERENCE_TYPE contains "Transfer", REFERENCE_ID points to a Transfer ID (PF.BI.S_TRANSFERS.ID). When REFERENCE_TYPE contains "Invoice", REFERENCE_ID points to an Invoice ID (PF.BI.S_INVOICES.ID)
- CREATOR_NAME
  - Meaning: Display name of the creator payee
  - Synonyms: creator, influencer, talent, ambassador, connected account, connected account name, creator name, content creator
  - Examples: "Katie Reardon", "Milan & Romana Outfluencers", "Jess Cohen"
- COMPANY_NAME
  - Meaning: Paying company/customer
  - Synonyms: brand, customer
  - Examples: "Ambrook", "Popfly Inc", "ROLL Recovery"
- CAMPAIGN_NAME
  - Meaning: Campaign associated with the payment
  - Synonyms: campaign, program, project
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
  - Synonyms: creator, influencer, talent, ambassador, connected account, connected account name, creator name, content creator
  - Examples: "Reardon Land and Cattle LLC", "Uproot and Adventure", "Jessica Cohen"
- USER_ID
  - Meaning: Popfly user identifier associated to the creator
  - Synonyms: user id
  - Examples: 8789, 8157, 8859
  - Relationships: PF.BI.PF_CONTENTCREATORS.USERID, PF.BI.PF_ASPNETUSERS.ID

## Typical questions and correct SQL patterns
- Show payments by amount range and date
- Top creators by payment volume
- Invoices by status and company
- Payment totals by company and period
- Payments for specific brand/campaign
- High-value payments by creator
- Payment volumes by business mode
- Uncategorized payments
- Agency mode payments by customer
- Payment status by creator
- Payment status by creator and campaign
- Total payments by campaign
- Unpaid invoices by campaign
- "Show labs payments" → `SELECT * FROM MV_CREATOR_PAYMENTS_UNION WHERE PAYMENT_TYPE = 'Agency Mode'`
- "List Popfly Labs invoices" → `SELECT * FROM MV_CREATOR_PAYMENTS_UNION WHERE PAYMENT_TYPE = 'Agency Mode' AND REFERENCE_TYPE LIKE '%Invoice%'`
- "PAKA creator payment totals by campaign" → `SELECT CAMPAIGN_NAME, SUM(PAYMENT_AMOUNT) FROM MV_CREATOR_PAYMENTS_UNION WHERE COMPANY_NAME = 'PAKA' GROUP BY CAMPAIGN_NAME`
- "ALPAKA payments" → `SELECT * FROM MV_CREATOR_PAYMENTS_UNION WHERE COMPANY_NAME = 'ALPAKA'`
- "Show PAKA invoices" → `SELECT * FROM MV_CREATOR_PAYMENTS_UNION WHERE COMPANY_NAME = 'PAKA' AND REFERENCE_TYPE LIKE '%Invoice%'`
- "agency services total" → `SELECT SUM(PAYMENT_AMOUNT) FROM MV_CREATOR_PAYMENTS_UNION WHERE PAYMENT_TYPE = 'Agency Mode'`
- "agency payments" → `SELECT * FROM MV_CREATOR_PAYMENTS_UNION WHERE PAYMENT_TYPE = 'Agency Mode'`
- "self-serve payments" → `SELECT * FROM MV_CREATOR_PAYMENTS_UNION WHERE PAYMENT_TYPE = 'Direct Mode'`
- "platform invoice amounts" → `SELECT PAYMENT_AMOUNT FROM MV_CREATOR_PAYMENTS_UNION WHERE PAYMENT_TYPE = 'Direct Mode'`
- "direct business invoices" → `SELECT * FROM MV_CREATOR_PAYMENTS_UNION WHERE PAYMENT_TYPE = 'Direct Mode' AND REFERENCE_TYPE LIKE '%Invoice%'`

## Sensitive data
- Do not surface internal IDs beyond REFERENCE_ID and Stripe IDs already exposed in this view.

## Defaults
- LIMIT 1000
- ORDER BY PAYMENT_DATE DESC
- Time window fallback: >= January 1, 2025
- Currency: USD; Timezone: UTC