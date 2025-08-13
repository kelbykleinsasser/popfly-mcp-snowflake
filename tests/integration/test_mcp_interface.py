#!/usr/bin/env python3
"""
Test synonym translations through the actual MCP HTTP interface
This will properly log to AI_USER_ACTIVITY_LOG
"""
import requests
import json
import os
from typing import Dict, Any

# Get the API key
API_KEY = os.getenv('OPEN_WEBUI_API_KEY')
if not API_KEY:
    # Try to get from GCP Secret Manager
    import subprocess
    result = subprocess.run(
        ['gcloud', 'secrets', 'versions', 'access', 'latest', 
         '--secret=OPEN_WEBUI_API_KEY', '--project=popfly-mcp-servers'],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        API_KEY = result.stdout.strip()

BASE_URL = "http://localhost:8000"  # For local testing
# BASE_URL = "https://mcp.popfly.com"  # For production

def call_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict:
    """Call an MCP tool through the HTTP interface"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "name": tool_name,
        "arguments": arguments
    }
    
    # Use the appropriate group endpoint
    # For admins group (has query_payments access)
    response = requests.post(
        f"{BASE_URL}/admins/tools/call",
        headers=headers,
        json=payload
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": f"HTTP {response.status_code}: {response.text}"}

def test_payment_query(query: str):
    """Test a payment query through MCP"""
    print(f"\nQuery: {query}")
    print("-" * 60)
    
    result = call_mcp_tool("query_payments", {
        "natural_language_query": query,
        "max_rows": 10
    })
    
    if "error" in result:
        print(f"❌ Error: {result['error']}")
    elif result.get("success"):
        content = result.get("content", [])
        if content and len(content) > 0:
            text = content[0].get("text", "")
            # Extract just the first part of the response
            lines = text.split('\n')
            for line in lines[:5]:  # Show first 5 lines
                print(line)
            if len(lines) > 5:
                print("...")
    else:
        print(f"❌ Failed: {result}")

def main():
    if not API_KEY:
        print("❌ No API key found. Set OPEN_WEBUI_API_KEY environment variable")
        return
    
    print("Testing Payment Queries through MCP HTTP Interface")
    print("=" * 60)
    print(f"Using: {BASE_URL}")
    print(f"API Key: {API_KEY[:10]}...")
    
    # Test synonym queries
    test_queries = [
        "Show payments for labs",
        "Total for Popfly Labs business model",
        "List agency services payments",
        "Show payments for ambassadors",
        "List all influencer invoices",
        "self-serve payment totals",
        "platform payments",
    ]
    
    for query in test_queries:
        test_payment_query(query)
    
    print("\n" + "=" * 60)
    print("✅ All queries sent through MCP interface")
    print("Check AI_USER_ACTIVITY_LOG for logged entries")

if __name__ == "__main__":
    main()