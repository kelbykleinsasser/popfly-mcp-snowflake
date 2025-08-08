# Traditional MCP Server (what we're NOT doing):
# User asks: "Show me pending payments over $500 for creators whose names start with J from last month"

# LLM has to:
# 1. Parse the complex query
# 2. Choose from many tools: search_by_status? filter_by_amount? search_by_creator_pattern?
# 3. Possibly chain multiple tool calls
# 4. Hope the parameters align with the user's intent

tools = [
    "search_payments_by_status",
    "filter_payments_by_amount_range", 
    "search_payments_by_creator_name",
    "filter_payments_by_date_range",
    "search_payments_by_creator_pattern",
    # ... 20 more specific tools
]

# Our Approach (what we ARE doing):
# User asks: "Show me pending payments over $500 for creators whose names start with J from last month"

# LLM simply calls:
def query_payments_example():
    """Example of our approach"""
    query = "Show me pending payments over $500 for creators whose names start with J from last month"
    
    # Cortex generates:
    generated_sql = """
    SELECT * FROM V_CREATOR_PAYMENTS_UNION 
    WHERE PAYMENT_STATUS = 'pending' 
      AND PAYMENT_AMOUNT > 500 
      AND CREATOR_NAME LIKE 'J%'
      AND PAYMENT_DATE >= DATEADD(month, -1, CURRENT_DATE())
    ORDER BY PAYMENT_DATE DESC
    LIMIT 1000
    """
    
    return generated_sql
