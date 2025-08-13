#!/usr/bin/env python3
"""
Test PAKA query through API
"""
import requests
import json

url = "https://mcp.popfly.com/admins/tools/call"
headers = {
    "Authorization": "Bearer sk-snowflake-mcp-dZOl9vjv2Ylcg8oT0LLmumh3S9ugU6x2jdVmXVoqJqU",
    "Content-Type": "application/json"
}

query = "show me the PAKA creator payment totals by campaign"

data = {
    "name": "query_payments",
    "arguments": {
        "query": query,
        "max_rows": 100
    }
}

print(f"Testing query: {query}")
print("-" * 80)

response = requests.post(url, json=data, headers=headers)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    result = response.json()
    
    if result.get('success') and result.get('content'):
        text = result['content'][0]['text'] if isinstance(result['content'], list) else result['content']
        
        # Extract SQL
        if "Generated SQL:" in text:
            sql_start = text.find("Generated SQL: `") + len("Generated SQL: `")
            sql_end = text.find("`", sql_start)
            if sql_end > sql_start:
                generated_sql = text[sql_start:sql_end]
                print(f"\nGenerated SQL:\n{generated_sql}\n")
                
                # Check matching pattern
                if "= 'PAKA'" in generated_sql:
                    print("✅ GOOD: Using exact match = 'PAKA'")
                elif "LIKE '%PAKA%'" in generated_sql.upper():
                    print("❌ PROBLEM: Still using LIKE '%PAKA%'")
                else:
                    print("⚠️  CHECK: Unclear matching pattern")
        
        # Parse results
        json_end = text.find("\n\n**")
        if json_end == -1:
            json_end = len(text)
        json_str = text[:json_end]
        
        try:
            results = json.loads(json_str)
            print(f"\nResults ({len(results)} rows):")
            
            for i, row in enumerate(results[:5]):  # Show first 5
                print(f"  {row}")
            
            if len(results) > 5:
                print(f"  ... and {len(results) - 5} more rows")
                
        except json.JSONDecodeError:
            print("Could not parse results as JSON")
            print(f"Raw response: {text[:500]}...")
else:
    print(f"Error: {response.text}")