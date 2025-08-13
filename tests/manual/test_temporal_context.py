#!/usr/bin/env python3
"""
Test script to verify temporal context is included in responses
"""
import requests
import json

url = "https://mcp.popfly.com/admins/tools/call"
headers = {
    "Authorization": "Bearer sk-snowflake-mcp-dZOl9vjv2Ylcg8oT0LLmumh3S9ugU6x2jdVmXVoqJqU",
    "Content-Type": "application/json"
}

# Test query about "this month"
data = {
    "name": "query_payments",
    "arguments": {
        "query": "Total Agency Mode payments this month",
        "max_rows": 10
    }
}

print("Testing temporal context for 'this month' query...")
print(f"Query: {data['arguments']['query']}")
print("-" * 80)

response = requests.post(url, json=data, headers=headers)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    result = response.json()
    
    # Check if temporal context is present
    if 'content' in result and result['content']:
        content = result['content'][0]['text'] if isinstance(result['content'], list) else result['content']
        
        # Look for temporal markers
        import datetime
        current_month = datetime.datetime.now().strftime('%B %Y')
        
        if current_month in content:
            print(f"✅ SUCCESS: Temporal context found ({current_month})")
        elif "Time Period:" in content:
            print(f"✅ SUCCESS: Temporal context marker found")
        else:
            print(f"⚠️  WARNING: No explicit temporal context found")
            print(f"Expected to see: {current_month}")
        
        # Check for SQL query
        if "Generated SQL:" in content:
            print("✅ SUCCESS: SQL query included for transparency")
        else:
            print("⚠️  WARNING: SQL query not included")
        
        print("\nFull response:")
        print(json.dumps(result, indent=2))
else:
    print(f"Error: {response.text}")