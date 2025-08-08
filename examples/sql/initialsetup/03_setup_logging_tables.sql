-- File: examples/sql/initialsetup/03_setup_logging_tables.sql
-- Example of what gets logged in AI_USER_ACTIVITY_LOG for Cortex tracking
-- This shows the structure of the ACTION_DETAILS JSON column

-- Example log entry structure (for reference):
/*
{
    "tool_name": "query_payments",
    "query_type": "cortex_generated",
    "natural_language_query": "Show payments over $1000 last month",
    "generated_sql": "SELECT * FROM V_CREATOR_PAYMENTS_UNION WHERE...",
    "cortex_model": "llama3.1-70b",
    "generation_time_ms": 850,
    "validation_passed": true,
    "row_count": 150
}
*/

-- Note: AI_USER_ACTIVITY_LOG, AI_CORTEX_USAGE_LOG, AI_SCHEMA_METADATA, and AI_BUSINESS_CONTEXT
-- are assumed to already exist in the PF.BI schema. This file documents their usage patterns.

-- AI_CORTEX_USAGE_LOG tracks:
-- - Every COMPLETE function call
-- - Token usage and costs
-- - Success/failure rates
-- - Query patterns for optimization

-- AI_SCHEMA_METADATA contains:
-- - Column documentation with business meaning
-- - Example values for better SQL generation
-- - Column relationships
-- - Common query patterns per column

-- AI_BUSINESS_CONTEXT includes:
-- - Business rules affecting query logic
-- - Common analysis patterns
-- - Domain-specific terminology
-- - Query interpretation guidelines
