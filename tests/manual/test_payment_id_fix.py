#!/usr/bin/env python3
"""
Test script to verify that the PAYMENT_ID column hallucination fix is working
"""
import requests
import json

url = "https://mcp.popfly.com/admins/tools/call"
headers = {
    "Authorization": "Bearer sk-snowflake-mcp-dZOl9vjv2Ylcg8oT0LLmumh3S9ugU6x2jdVmXVoqJqU",
    "Content-Type": "application/json"
}

# This query previously failed because Cortex would generate COUNT(PAYMENT_ID)
data = {
    "name": "query_payments",
    "arguments": {
        "query": "show me the total amount and count of payments broken down by payment type (agency mode vs direct mode) for all of 2025",
        "max_rows": 1000
    }
}

print("Testing query that previously caused PAYMENT_ID hallucination...")
print(f"Query: {data['arguments']['query']}")
print("-" * 80)

response = requests.post(url, json=data, headers=headers)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    result = response.json()
    
    # Check if the generated SQL is in the response
    if 'generated_sql' in str(result):
        # Extract the generated SQL if present
        import re
        sql_match = re.search(r'Generated SQL:\s*([^\\n]+)', str(result))
        if sql_match:
            generated_sql = sql_match.group(1)
            print(f"\nGenerated SQL: {generated_sql}")
            
            # Check if it's using the correct column
            if 'PAYMENT_ID' in generated_sql.upper():
                print("❌ FAILED: Still using non-existent PAYMENT_ID column")
            elif 'COUNT(REFERENCE_ID)' in generated_sql.upper() or 'COUNT(*)' in generated_sql.upper():
                print("✅ SUCCESS: Using correct column for counting")
            else:
                print("⚠️  CHECK: Verify the COUNT clause is correct")
    
    # Pretty print the full response
    print("\nFull response:")
    print(json.dumps(result, indent=2))
else:
    print(f"Error: {response.text}")