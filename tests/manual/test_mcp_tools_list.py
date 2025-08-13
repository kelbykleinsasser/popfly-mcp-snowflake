#!/usr/bin/env python3
"""
Test script to verify that read_query is NOT exposed in list_tools
"""
import requests
import json

url = "https://mcp.popfly.com/tools"
headers = {
    "Authorization": "Bearer sk-snowflake-mcp-dZOl9vjv2Ylcg8oT0LLmumh3S9ugU6x2jdVmXVoqJqU",
    "Content-Type": "application/json"
}

print("Testing list_tools endpoint to ensure read_query is NOT exposed...")
print("-" * 80)

response = requests.get(url, headers=headers)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    result = response.json()
    
    # Extract tool names
    tool_names = []
    if isinstance(result, dict) and 'tools' in result:
        tools = result['tools']
        for tool in tools:
            if isinstance(tool, dict) and 'name' in tool:
                tool_names.append(tool['name'])
    elif isinstance(result, list):
        for tool in result:
            if isinstance(tool, dict) and 'name' in tool:
                tool_names.append(tool['name'])
    
    print(f"\nFound {len(tool_names)} tools:")
    for name in tool_names:
        print(f"  - {name}")
    
    # Check for read_query
    if 'read_query' in tool_names:
        print("\n❌ FAILED: read_query is exposed in list_tools (it should be internal-only)")
    else:
        print("\n✅ SUCCESS: read_query is NOT exposed in list_tools")
    
    # Check that query_payments is present
    if 'query_payments' in tool_names:
        print("✅ SUCCESS: query_payments is available")
    else:
        print("❌ FAILED: query_payments is missing")
    
    print("\nFull response:")
    print(json.dumps(result, indent=2))
else:
    print(f"Error: {response.text}")