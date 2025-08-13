#!/usr/bin/env python3
import requests
import json

url = "https://mcp.popfly.com/admins/tools/call"
headers = {
    "Authorization": "Bearer sk-snowflake-mcp-dZOl9vjv2Ylcg8oT0LLmumh3S9ugU6x2jdVmXVoqJqU",
    "Content-Type": "application/json"
}
data = {
    "name": "query_payments",
    "arguments": {
        "query": "Show me the top 3 Agency Mode payments by amount",
        "max_rows": 3
    }
}

response = requests.post(url, json=data, headers=headers)
print(f"Status: {response.status_code}")
print(json.dumps(response.json(), indent=2))