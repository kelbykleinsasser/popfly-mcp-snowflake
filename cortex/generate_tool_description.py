#!/usr/bin/env python3
"""
Generate enriched tool descriptions from narrative data for LLM understanding.
"""

def generate_payment_tool_description():
    """Generate a comprehensive tool description from the narrative"""
    
    description = """Query Creator payments and invoices using natural language. This tool understands complex payment scenarios including:

PAYMENT TYPES:
• Agency Mode: Popfly agency services where we source/pay creators and invoice customers
• Direct Mode: Platform transactions between customers and creators
• Unassigned: Catch-all for uncategorized payments

KEY ENTITIES YOU CAN QUERY:
• Creators (by name, Stripe account, or user ID)
• Companies/Customers (by name, Stripe customer ID)
• Campaigns/Projects (by name)
• Payment amounts, dates, and statuses

UNDERSTANDS PAYMENT TERMINOLOGY:
• "Payments" = actual money transferred (PAYMENT_STATUS='paid')
• "Invoices" = bills from creators (any PAYMENT_STATUS)
• "Transfers" = payments to creators
• Status values: paid, pending, open, failed

EXAMPLE QUERIES:
• "Show Agency Mode payments over $500 from last 30 days"
• "List pending Direct Mode invoices for Ambrook"
• "Top 5 creators by payment amount in 2025"
• "Which creators have unpaid invoices for Campaign X?"
• "Total payments by company this month"
• "Show all payments to Jordan Kahana"

DATA COVERAGE: January 2025 onwards only (earlier data unreliable)
DEFAULT LIMIT: 1000 rows
TIMEZONE: UTC"""
    
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language query about creator payments, invoices, or transfers. Can reference creators, companies, campaigns, amounts, dates, payment types (Agency/Direct Mode), and statuses (paid/pending/open/failed).",
                "examples": [
                    "Show all Agency Mode payments over $1000",
                    "List pending invoices for creator 'Katie Reardon'",
                    "Total payments by campaign for Direct Mode",
                    "Which creators have been paid this month?",
                    "Unpaid invoices older than 30 days"
                ]
            },
            "max_rows": {
                "type": "integer",
                "description": "Maximum rows to return (1-10000). Default 1000.",
                "default": 1000,
                "minimum": 1,
                "maximum": 10000
            }
        },
        "required": ["query"],
        "additionalProperties": False
    }
    
    return description, input_schema


def generate_update_sql():
    """Generate SQL to update the tool in the database"""
    
    description, input_schema = generate_payment_tool_description()
    
    # Escape single quotes for SQL
    description_escaped = description.replace("'", "''")
    
    import json
    input_schema_json = json.dumps(input_schema, indent=2)
    
    sql = f"""
-- Update query_payments tool with enriched description from narrative
UPDATE PF.BI.AI_MCP_TOOLS
SET 
    TOOL_DESCRIPTION = '{description_escaped}',
    INPUT_SCHEMA = PARSE_JSON('{input_schema_json}'),
    UPDATED_AT = CURRENT_TIMESTAMP()
WHERE TOOL_NAME = 'query_payments';

-- Verify the update
SELECT 
    TOOL_NAME,
    LENGTH(TOOL_DESCRIPTION) as DESC_LENGTH,
    UPDATED_AT
FROM PF.BI.AI_MCP_TOOLS
WHERE TOOL_NAME = 'query_payments';
"""
    
    return sql


if __name__ == "__main__":
    print("=== Enhanced Tool Description ===\n")
    description, schema = generate_payment_tool_description()
    print(description)
    print("\n=== SQL Update Statement ===\n")
    print(generate_update_sql())