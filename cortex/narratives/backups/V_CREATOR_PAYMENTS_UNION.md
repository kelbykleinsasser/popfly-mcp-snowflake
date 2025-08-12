# Narrative: PF.BI.MV_CREATOR_PAYMENTS_UNION

- View/Table: PF.BI.MV_CREATOR_PAYMENTS_UNION (domain: creator_payments)
- Purpose: Unified analytics view for Creator payments (AKA invoice payment, transfer, balance transfer, payment) and Invoices (AKA creator invoice, creator bill, bill) using data sourced primarily from Stripe data (PF.BI.S_*), but also with extensive joins to Popfly data (PF.BI.PF_*, PF.BI.MV_*, PF.BI.CP_*). 


## Business rules
- Allowed operations: SELECT, WHERE, GROUP BY, ORDER BY, LIMIT
- Heavily favor querying only PF.BI.MV_CREATOR_PAYMENTS_UNION for most inquires, and join to other explicitly referenced tables or views only as a last resort
- Forbidden: Updates, deletes, DDL
- Always include LIMIT (default 1000)
- Timezone: UTC; Date types: TIMESTAMP_NTZ
- Default time window if none provided: January 2025 and later
- Preferred date column for recency: PAYMENT_DATE over CREATED_DATE
- Canonical PAYMENT_STATUS values: paid, pending, open, failed
- Canonical PAYMENT_TYPE values: Agency Mode, Direct Mode, Unassigned
- PAYMENT_TYPE value synonyms: Direct Mode (Self-Serve, Self Serve, Self Service, Platform, Customer), Agency Mode (Popfly Labs, Agency Services)
- Safe sorts: PAYMENT_DATE DESC, PAYMENT_AMOUNT DESC, CREATOR_NAME ASC
- Note: View contains both invoices (creator bills) and transfers (payments to creators)
- PAYMENT_TYPE carries considerable weight in this context. The PAYMENT_TYPE column contains the designations Agency Mode, Direct Mode, and Unassigned. Agency Mode represents Popfly  agency services (Popfly Labs, labs, agency) where we source and pay creators, and later invoice customers once campaigns (projects) have been completed; Direct Mode represents direct customer-creator relationships where Popfly is merely providing the platform upon which transactions take place. Creators "apply" to Campaigns and once accepted can create and submit content, interact with the Customer users on the platform, submit invoices, and get paid.
- PAYMENT_TYPE = "Unassigned" are not to be ignored. They are a catch all for invoices that don't fit neatly into Agency Mode or Direct Mode. These records should be transient as occassional data hygeine processes add necessary categorization data to move them to either Direct Mode or Agency Mode.
- Reasonably good Creator Invoice and Transfer data management began taking place starting around January 1, 2025. Never return Invoice or Transfer data from before this period.
- The term Customer can mean more than one thing on our platform. First, in Agency Mode, the Customer is Popfly's Customer because they're paying us to perform a service for them. In the case of Direct Mode, a Customer is both a subscriber to Popfly (they pay us a monthly fee to access Creators and use our platform) and a Customer is also the Customer to the Creator who is performing the services and will invoice the Customer directly.
- PF.BI.MV_CREATOR_PAYMENTS_UNION uses PF.BI.V_LOOKUP_AGENCYMODECLIENTIDS to separate Customers into Direct Mode and Agency Mode whereby if the STRIPE_CUSTOMER_ID appears in PF.BI.V_LOOKUP_AGENCYMODECLIENTIDS they are designated as for Agency Mode Customers. If not, they are designated as Direct Mode Customers. 
- Not all Invoices are connected to Campaigns (AKA projects). Some Invoices are issued by creators without a reference to a Campaign. These can be identified by REFERENCE_TYPE = "Invoice (No Campaign)". This is problematic to the degree that Agency Mode clients like to receive Popfly Invoices that show each Creator along with the Campaign the Creator fee is intended to cover. This is for their internal budgeting purposes so they can more easily distinguish the marketing ROI.
- It's quite common for Creators to issue multiple Invoices for the same project for not other reason than that they think that it will get them paid more quickly, or they believe that somehow either we or their Direct Mode customer forgot to pay them. Sometimes duplicate Invoices are issued with one showing REFERENCE_TYPE = "Invoice (No Campaign)" and the other REFERENCE_TYPE = "Invoice" (which is connected to a Campaign). The reality is that they have almost no other recourse and as such it's understandable when they take the only action that they can take, but this leads to corrupt--or at minimum, unclear--data.
- Creators can be identified in this dataset by--most commonly--CREATOR_NAME and STRIPE_CONNECTED_ACCOUNT_NAME. It's possible that users may also want to find Creators by STRIPE_CONNECTED_ACCOUNT_ID or even USER_ID from time to time.
- REFERENCE_ID means two different things depending upon the value in REFERENCE_TYPE. When REFERENCE_TYPE contains "Transfer", REFERENCE_ID points to a Transfer ID (PF.BI.S_TRANSFERS.ID). When REFERENCE_TYPE contains "Invoice", REFERENCE_ID points to an Invoice ID (PF.BI.S_INVOICES.ID).
- CREATED_DATE represents two different things depending upon REFERENCE_TYPE. When REFERENCE_TYPE contains "Transfer", the CREATED_DATE represents the date that funds were transferred from either Popfly (our company) or a Customer (in rare cases), representing a Creator Payment. When REFERENCE_TYPE contains "Invoice" CREATED_DATE represents the date that the Creator issued the Invoice. Unfortunately this date is not entirely useful because there are no standards in place as to when Creator's decide to submit invoices for their work. Some Creators will issues Invoices at the moment they are accepted to a Campaign--long before they have actually completed their work--and as such it renders the due data meaningless. As of August 1st, 2025 we are underway with a project that will simplify the process of identifying Invoices that are actually due for payment. These "approvals" will be issued by Account Managers and stored in a table called PF.BI.CP_PAYMENT_APPROVALS. If the user mentions anything about "approval", they are most likely talking about data in this table, which again at the moment is sparse.
- PAYMENT_DATE is the actual date that payment occured either through a Transfer or Invoice Payment. PAYMENT_DATE is always null when an invoice has not yet been paid. When a user asks to see Creator Payments, they are referring to actual payments where PAYMENT_DATE is not null. When a user asks to see Creator Invoices, they are asking for Invoices where PAYMENT_STATUS contains "paid", "open", "unpaid".
- Companies (AKA company, client, customer, brand) can be identified by COMPANY_NAME, and STRIPE_CUSTOMER_NAME. Less commonly, users may want to look up Invoices and Transfers by CAMPAIGN_NAME (sometimes CAMPAIGN_NAME contains the name of the company), or even less commonly by STRIPE_CUSTOMER_ID.
- PAYMENT_AMOUNT is always the Invoice amount when PAYMENT_STATUS<>'paid'. In these cases these should not be referred to as payments as they are only invoices. When PAYMENT_STATUS='paid' the amount is either the Invoice amount (PAYMENT_TYPE="Direct Mode") or Transfer amount (PAYMENT_TYPE="Agency Mode")


## Key columns
- PAYMENT_STATUS
  - Meaning: State of the payment lifecycle, always "paid" when REFERENCE_TYPE contains "Transfer".
  - Synonyms: status, state, invoice status, payment status, creator payment status, creator invoice status
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
  - Meaning: Business model classification for creator payments and invoices
  - Synonyms: agency payments, agency invoices, agency transfers, labs invoice, labs payments, project payments, creator payments, direct payments, direct invoices
  - Examples: Agency Mode, Direct Mode, Unassigned
- REFERENCE_TYPE
  - Meaning: Upstream object type
  - Synonyms: source type
  - Examples: Invoice, Transfer
- REFERENCE_ID
  - Meaning: Upstream object identifier
  - Synonyms: source id, invoice id, transfer id
  - Examples: in_1REYjj..., in_1RrQUU..., tr_1ReiGM...
  - Relationships: When REFERENCE_TYPE contains "Transfer", REFERENCE_ID points to a Transfer ID (PF.BI.S_TRANSFERS.ID). When REFERENCE_TYPE contains "Invoice", REFERENCE_ID points to an Invoice ID (PF.BI.S_INVOICES.ID)
- CREATOR_NAME
  - Meaning: Display name of the creator payee
  - Synonyms: creator, influencer, talent, ambassador, connected account
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
- Agency Mode vs Direct Mode payment volumes by month
- Unassigned payments that need categorization
- Agency Mode creator payments for Popfly Labs customers
- What is the status of payment to CREATOR_NAME
- What is the status of payment to CREATOR_NAME for CAMPAIGN_NAME
- How  much have we paid out to creators for CAMPAIGN_NAME
- Show all unpaid invoices for creators for CAMPAIGN_NAME
- Has CREATOR_NAME been approved for payment for CAMPAIGN NAME
- Show all approved, unpaid invoices for CREATOR_NAME
- Show all approved, unpaid invoices for CAMPAIGN_NAME
- Show all approved, unpaid invoices for COMPANY_NAME

## Sensitive data
- Do not surface internal IDs beyond REFERENCE_ID and Stripe IDs already exposed in this view.

## Defaults
- LIMIT 1000
- ORDER BY PAYMENT_DATE DESC
- Time window fallback: >= January 1, 2025
- Currency: USD; Timezone: Pacific Time