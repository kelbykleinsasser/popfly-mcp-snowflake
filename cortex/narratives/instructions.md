# Processing Instructions for `cortex/narratives/<VIEW_NAME>.md`

These instructions define exactly how to turn a narrative Markdown file into database metadata that powers Cortex prompts. Lineage is intentionally out of scope here.

## Scope and goals
- Convert a single narrative file into structured records in:
  - `PF.BI.AI_SCHEMA_METADATA` (column semantics)
  - `PF.BI.AI_BUSINESS_CONTEXT` (domain context + examples)
  - `PF.BI.AI_CORTEX_PROMPTS` (optional prompt override; otherwise use code default)
- Enforce consistency, idempotency, and validation.
- Keep prompts compact; DB holds full detail.

## File placement and naming
- Location: `cortex/narratives/<VIEW_NAME>.md`
- One file per view/table. Example: `cortex/narratives/V_CREATOR_PAYMENTS_UNION.md`

## Required sections in the Markdown file
Use these headings and blocks (order can vary; extra sections are ignored):

- Top matter (first lines)
  - `- View/Table: <DB>.<SCHEMA>.<VIEW> (domain: <domain_key>)`
  - `- Purpose: <one or two sentences>`

- `## Business rules`
  - Bulleted list of constraints and defaults. Examples:
    - Allowed operations: SELECT, WHERE, GROUP BY, ORDER BY, LIMIT
    - Always include LIMIT (default 1000)
    - No joins/CTEs/subqueries
    - Timezone, date type
    - Default time window if none provided
    - Canonical enum values (e.g., `PAYMENT_STATUS: paid|pending|open|failed`)
    - Safe sorts
    - Forbidden operations/terms

- `## Key columns`
  - Repeated blocks, one per column:
    - `- <COLUMN_NAME>`
      - `- Meaning: <plain-English meaning>`
      - `- Synonyms: <comma-separated>`
      - `- Examples: <comma-separated representative values>`
      - `- Relationships: <free-form note or leave blank>`

- `## Typical questions`
  - 3–10 example natural-language questions (bulleted lines).

- `## Sensitive data`
  - What to exclude from prompts/results (bulleted lines or sentence).

- `## Defaults`
  - LIMIT, ORDER BY, fallback window, currency, timezone, etc.

Notes:
- Headings are matched case-insensitively.
- Extra whitespace is tolerated.
- Missing sections cause validation warnings (see below).

## Parsing rules (strict but forgiving)
- `View/Table` line must include fully-qualified name and a domain in parentheses: `(<domain_key>)`.
- `Business rules` are captured as plain text (one per bullet).
- In `Key columns`:
  - `Meaning` becomes `BUSINESS_MEANING`.
  - `Synonyms` → split on commas → `KEYWORDS ARRAY`.
  - `Examples` is stored as a short JSON-ish string; keep concise.
  - `Relationships` is copied verbatim into `RELATIONSHIPS` (optional).
- `Typical questions` lines are stored as examples in the business context.
- `Sensitive data` is not stored in DB (used only to lint and for future policy).
- `Defaults` lines are stored in business context text block (for prompt hints).

## Database writes (idempotent upserts)
- Resolve target from the file’s `View/Table` line. Defaults:
  - `database = settings.snowflake_database`
  - `schema = settings.snowflake_schema`
- Validate that `<VIEW_NAME>` exists with `DESCRIBE TABLE`. Unknown columns are ignored with a warning.

### AI_SCHEMA_METADATA
- Upsert per column:
  - Key: `(TABLE_NAME = <VIEW_NAME>, COLUMN_NAME)`
  - Fields set/updated:
    - `BUSINESS_MEANING` from `Meaning`
    - `KEYWORDS` (ARRAY) from `Synonyms`
    - `EXAMPLES` (short string from `Examples`)
    - `RELATIONSHIPS` (free-form; optional)
- If row missing, insert with a new `ID` (`COALESCE(MAX(ID),0)+1`).

### AI_BUSINESS_CONTEXT
- Upsert single row per domain:
  - Key: `(DOMAIN)`
  - Fields:
    - `TITLE` = `<VIEW_NAME> Context` (or parsed title)
    - `DESCRIPTION` = `Purpose + consolidated rules + defaults`
    - `KEYWORDS` = union of distinct synonyms across key columns (ARRAY)
    - `EXAMPLES` = bullet list joined from `Typical questions`

### AI_CORTEX_PROMPTS (optional)
- Only insert if you explicitly include a `## Prompt override` section (optional). Otherwise, rely on code default.
- Insert a single active prompt with simple token placeholders:
  - `PROMPT_TEMPLATE` should use tokens: `[[VIEW_NAME]]`, `[[ALLOWED_COLUMNS]]`, `[[ALLOWED_OPS]]`, `[[MAX_ROWS]]`, `[[BUSINESS_RULES]]`, `[[RELEVANT_COLUMN_SNIPPETS]]`, `[[USER_QUERY]]`.
  - Set `MODEL_NAME=settings.cortex_model`, `TEMPERATURE=0.1`, `MAX_TOKENS=1200`, `IS_ACTIVE=TRUE`.
- If an active prompt already exists, skip override unless `Prompt override` contains `override: true`.

## Validation and linting
- Fail if `View/Table` is missing or malformed.
- Warn if any `Key columns` are not present in `DESCRIBE TABLE` results.
- Check that business rules include at least:
  - allowed operations
  - explicit LIMIT policy
- Trim any single example list longer than ~200 chars.
- Ensure no forbidden ops appear (`DROP/DELETE/INSERT/UPDATE/ALTER/CREATE`).

## Prompt consumption (how the code uses this)
- `utils.prompt_builder.PromptBuilder` loads:
  - Business context (rules, defaults, examples) using `DOMAIN` from the header
  - Column snippets from `AI_SCHEMA_METADATA` (`BUSINESS_MEANING`, `EXAMPLES`)
  - Active prompt from `AI_CORTEX_PROMPTS` if present; otherwise uses the built-in default
- At runtime we keep prompts compact (top 8–12 columns), but all detail persists in DB.

## Processing checklist
1) Read `cortex/narratives/<VIEW>.md`.
2) Parse required sections and normalize values.
3) Resolve `<VIEW>` and fetch actual columns via `DESCRIBE TABLE`.
4) Begin a transaction.
5) Upsert `AI_BUSINESS_CONTEXT` for the domain.
6) Upsert `AI_SCHEMA_METADATA` rows for listed columns (ignore unknowns, warn).
7) If `## Prompt override` is present, upsert `AI_CORTEX_PROMPTS` (respect existing active prompts unless `override: true`).
8) Commit.
9) Run a prompt preview (optional): call `PromptBuilder.build_prompt_for_view` with a sample query and inspect output.
10) Log actions to standard logs; DB audit optional.

## Example minimal narrative
```
- View/Table: PF.BI.V_CREATOR_PAYMENTS_UNION (domain: creator_payments)
- Purpose: Unified analytics view for creator payments.

## Business rules
- Allowed operations: SELECT, WHERE, GROUP BY, ORDER BY, LIMIT
- Always include LIMIT (default 1000)
- No joins/CTEs/subqueries
- Timezone: UTC; Date types: TIMESTAMP_NTZ
- Default time window: last 365 days
- Canonical PAYMENT_STATUS: paid|pending|open|failed

## Key columns
- PAYMENT_STATUS
  - Meaning: Payment lifecycle state
  - Synonyms: status,state
  - Examples: paid,pending,open,failed
  - Relationships:
- PAYMENT_AMOUNT
  - Meaning: Amount in USD
  - Synonyms: amount,value,$
  - Examples: 26.16,103.72,275
  - Relationships:

## Typical questions
- Show paid payments over $100 since last month by campaign
- Pending invoices by company for the past 90 days

## Sensitive data
- Exclude emails and bank details

## Defaults
- LIMIT 1000
- ORDER BY PAYMENT_DATE DESC
- Time window fallback: last 365 days
- Currency: USD; Timezone: UTC
```

## Notes
- This process is safe to repeat; upserts are idempotent.
- If a section is missing, proceed with defaults and emit a warning.
- Keep narratives short and concrete—DB holds the detail; prompts remain compact.
