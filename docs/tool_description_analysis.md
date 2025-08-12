# Tool Description Analysis and Recommendations

**Date:** 2025-08-12 12:30 PST

## Current Description Issues

Our current description is **4,809 characters** - this is problematic because:

1. **Too verbose** - LLMs perform better with concise, focused descriptions
2. **Buried key information** - The most important info (what the tool does) is lost in business details
3. **Repetitive** - Multiple bullet points about Agency Mode that could be condensed
4. **Missing clear trigger phrases** - Doesn't explicitly say "Use this tool when..."

## Current Description Structure
```
Unified view for Creator payments... [188 chars of technical details]
PAYMENT TYPES: [2,500+ chars of business rules]
KEY ENTITIES: [200 chars]
EXAMPLE QUERIES: [300 chars]
```

## Recommended Optimal Description

Based on best practices for Claude Sonnet:

```
Query creator payments and invoices using natural language. 

USE THIS TOOL WHEN: Users ask about payments, invoices, transfers, or financial transactions involving creators, companies, or campaigns.

UNDERSTANDS QUERIES LIKE:
• "Show me the 10 most recent creator invoices"
• "List payments to Jordan Kahana"
• "Total Agency Mode payments this month"
• "Pending invoices for Ambrook"
• "Top creators by payment amount"

SEARCHABLE DATA:
• Creators (by name, ID, or Stripe account)
• Companies/Customers (by name or Stripe ID)  
• Campaigns/Projects
• Payment types: Agency Mode (Popfly manages), Direct Mode (platform only), Unassigned
• Statuses: paid, pending, open, failed
• Date ranges (data from Jan 2025 onwards)

Returns up to 1000 rows by default. Queries are converted to SQL using Snowflake Cortex AI.
```

## Key Improvements

1. **Length**: ~650 characters (vs 4,809)
2. **Structure**: Clear "USE THIS TOOL WHEN" trigger
3. **Examples**: Concrete, simple queries the LLM can pattern match
4. **Essential info only**: Payment types summarized, not explained in detail
5. **Action-oriented**: Starts with what it does, not technical implementation

## Alternative Minimal Description

For testing if length is the issue:

```
Natural language search for creator payments, invoices, and transfers. Ask questions like "recent invoices", "payments to [creator name]", or "totals by company".
```

## Implementation Recommendation

1. **Create tiered descriptions**:
   - `TOOL_DESCRIPTION` - Concise for LLM (600-800 chars)
   - `TOOL_DESCRIPTION_DETAILED` - Full business context (current 4,809 chars)
   - `TOOL_DESCRIPTION_MINIMAL` - Ultra-short fallback (150 chars)

2. **Add explicit triggers** in description:
   - Start with "USE THIS TOOL FOR:"
   - Include negative cases: "DO NOT USE FOR: user management, authentication"

3. **Test incrementally**:
   - Start with minimal description
   - Add details until tool calling works reliably
   - Find the sweet spot between clarity and brevity

## SQL to Update

```sql
UPDATE PF.BI.AI_MCP_TOOLS
SET TOOL_DESCRIPTION = 'Query creator payments and invoices using natural language. 

USE THIS TOOL WHEN: Users ask about payments, invoices, transfers, or financial transactions involving creators, companies, or campaigns.

UNDERSTANDS QUERIES LIKE:
• "Show me the 10 most recent creator invoices"
• "List payments to Jordan Kahana"
• "Total Agency Mode payments this month"
• "Pending invoices for Ambrook"
• "Top creators by payment amount"

SEARCHABLE DATA:
• Creators (by name, ID, or Stripe account)
• Companies/Customers (by name or Stripe ID)
• Campaigns/Projects
• Payment types: Agency Mode, Direct Mode, Unassigned
• Statuses: paid, pending, open, failed
• Date ranges (data from Jan 2025 onwards)

Returns up to 1000 rows by default.',
UPDATED_AT = CURRENT_TIMESTAMP()
WHERE TOOL_NAME = 'query_payments';
```