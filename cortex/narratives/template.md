# Narrative Template (copy this file and fill for each view)

- View/Table: <DATABASE>.<SCHEMA>.<VIEW_OR_TABLE_NAME> (domain: <domain_key>)
- Purpose: <plain-English business purpose of this view/table>

## Business rules
- Allowed operations: SELECT, WHERE, GROUP BY, ORDER BY, LIMIT
- Always include LIMIT (default <default_limit, e.g., 1000>)
- No joins, subqueries, or CTEs; single-table queries only (unless explicitly allowed)
- Timezone: <UTC unless specified>; Date types: <e.g., TIMESTAMP_NTZ>
- Default time window if none provided: <e.g., last 365 days>
- Preferred date column for recency: <e.g., PAYMENT_DATE over CREATED_DATE>
- Canonical values: <list stable enumerations, e.g., PAYMENT_STATUS: paid|pending|open|failed>
- Safe sorts: <e.g., by PAYMENT_DATE DESC>, <fallbacks>
- Forbidden: <any forbidden terms/columns/operations>

## Key columns
- <COLUMN_NAME>
  - Meaning: <what it represents>
  - Synonyms: <comma-separated phrases users might say>
  - Examples: <comma-separated representative values>
  - Relationships: <mapping or source lineage>

(repeat the block above for each important column)

## Typical questions
- <example natural-language query>
- <example natural-language query>
- <example natural-language query>

## Sensitive data
- <what to exclude from prompts/results>

## Defaults
- LIMIT <N>
- ORDER BY <col> <ASC|DESC>
- Time window fallback: <e.g., last 365 days>
- Currency: <e.g., USD>; Timezone: <e.g., UTC>
