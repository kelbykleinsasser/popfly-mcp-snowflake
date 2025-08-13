#!/usr/bin/env python3
"""
Test production MCP server with comprehensive synonym tests
This will properly log all activities to AI_USER_ACTIVITY_LOG
"""
import requests
import json
import time
from typing import Dict, Any, List, Tuple
from datetime import datetime

# Production configuration
BASE_URL = "https://mcp.popfly.com"
API_KEY = "sk-snowflake-mcp-dZOl9vjv2Ylcg8oT0LLmumh3S9ugU6x2jdVmXVoqJqU"

def call_mcp_tool(tool_name: str, arguments: Dict[str, Any], group: str = "admins") -> Dict:
    """Call an MCP tool through the HTTP interface"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "name": tool_name,
        "arguments": arguments
    }
    
    response = requests.post(
        f"{BASE_URL}/{group}/tools/call",
        headers=headers,
        json=payload,
        timeout=30
    )
    
    if response.status_code == 200:
        result = response.json()
        # Normalize the response to always have success/error
        if 'success' in result:
            return result
        else:
            # Wrap raw response in our expected format
            return {"success": True, "content": [{"type": "text", "text": str(result)}]}
    else:
        return {"error": f"HTTP {response.status_code}: {response.text}"}

def extract_sql_from_response(result: Dict) -> str:
    """Extract generated SQL from MCP response"""
    if result.get("success"):
        content = result.get("content", [])
        if content and len(content) > 0:
            text = content[0].get("text", "")
            # Look for SQL in the response
            if "Generated SQL:" in text:
                sql_start = text.find("```sql")
                sql_end = text.find("```", sql_start + 6)
                if sql_start != -1 and sql_end != -1:
                    return text[sql_start + 6:sql_end].strip()
            elif "SELECT" in text.upper():
                # Try to extract SQL directly
                lines = text.split('\n')
                for i, line in enumerate(lines):
                    if "SELECT" in line.upper():
                        # Find the end of the SQL (usually ends with ; or Results:)
                        sql_lines = []
                        for j in range(i, len(lines)):
                            if lines[j].strip() and not lines[j].startswith("**"):
                                if "Results:" in lines[j] or "rows returned" in lines[j]:
                                    break
                                sql_lines.append(lines[j])
                        return '\n'.join(sql_lines).strip()
    return ""

def test_payment_query(query: str) -> Tuple[bool, str, str]:
    """Test a payment query through MCP
    Returns: (success, sql, error_message)
    """
    print(f"\nQuery: {query}")
    print("-" * 60)
    
    result = call_mcp_tool("query_payments", {
        "query": query,  # Changed from "natural_language_query" to "query"
        "max_rows": 10
    })
    
    if "error" in result and result["error"]:
        print(f"❌ Error: {result['error']}")
        return False, "", result['error']
    elif result.get("success"):
        # The response contains JSON data, not SQL
        content = result.get("content", [])
        if content and len(content) > 0:
            text = content[0].get("text", "")
            # Check if we got results (JSON array)
            if text.startswith('['):
                import json
                try:
                    data = json.loads(text)
                    if data and len(data) > 0:
                        # Check the PAYMENT_TYPE in the results
                        payment_types = set(row.get('PAYMENT_TYPE', '') for row in data)
                        print(f"✅ Success - Found {len(data)} results")
                        print(f"   Payment Types: {', '.join(payment_types)}")
                        return True, text, ""
                except:
                    pass
            print(f"⚠️  Success but unexpected response format")
            return True, text, ""
        else:
            print(f"⚠️  Success but no content")
            return True, "", "No content in response"
    else:
        error = result.get("error", result)
        print(f"❌ Failed: {error}")
        return False, "", str(error)

def analyze_synonym_translation(query: str, data: str, expected_value: str) -> str:
    """Analyze if synonym was correctly translated in the results"""
    if not data:
        return "NO_DATA"
    
    # Parse JSON data
    try:
        import json
        if data.startswith('['):
            results = json.loads(data)
            if results:
                # Check PAYMENT_TYPE values in results
                payment_types = set(row.get('PAYMENT_TYPE', '') for row in results)
                
                if expected_value in payment_types:
                    return "CORRECT"
                elif len(payment_types) > 0:
                    actual = ', '.join(payment_types)
                    return f"WRONG_TYPE:{actual}"
                else:
                    return "NO_PAYMENT_TYPE"
            else:
                return "NO_RESULTS"
    except:
        pass
    
    return "PARSE_ERROR"

def main():
    print("=" * 80)
    print("PRODUCTION MCP SERVER TEST")
    print("=" * 80)
    print(f"Server: {BASE_URL}")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"API Key: {API_KEY[:20]}...")
    
    # Test connectivity first
    print("\n" + "=" * 80)
    print("CONNECTIVITY TEST")
    print("-" * 80)
    
    health_result = call_mcp_tool("query_payments", {"query": "Show 1 recent payment", "max_rows": 1}, "admins")
    if health_result and "error" not in health_result and health_result.get('success'):
        print("✅ Server is accessible")
    elif health_result and health_result.get('success'):
        # Success but checking if we got data
        print("✅ Server is accessible and responding")
    else:
        error_msg = health_result.get('error', 'Unknown error') if health_result else 'No response'
        print(f"❌ Server error: {error_msg}")
        print(f"Full response: {health_result}")
        return
    
    # Business model synonym tests
    print("\n" + "=" * 80)
    print("BUSINESS MODEL SYNONYM TESTS")
    print("-" * 80)
    
    business_tests = [
        # Agency Mode (labs) synonyms
        ("Show payments for labs", "Agency Mode"),
        ("Total for Popfly Labs business model", "Agency Mode"),
        ("List agency services payments", "Agency Mode"),
        ("agency payments total", "Agency Mode"),
        ("labs invoice amounts", "Agency Mode"),
        
        # Direct Mode (self-serve) synonyms
        ("self-serve payment totals", "Direct Mode"),
        ("self serve creators", "Direct Mode"),
        ("platform payments", "Direct Mode"),
        ("direct business model", "Direct Mode"),
        ("self service invoices", "Direct Mode"),
    ]
    
    business_results = []
    for query, expected in business_tests:
        success, sql, error = test_payment_query(query)
        if success and sql:
            analysis = analyze_synonym_translation(query, sql, expected)
            business_results.append((query, expected, analysis))
            if analysis == "CORRECT":
                print(f"   ✅ Correctly translated to '{expected}'")
            elif analysis.startswith("INCORRECT"):
                incorrect_val = analysis.split(":")[1]
                print(f"   ❌ Used literal {incorrect_val} instead of '{expected}'")
            elif analysis == "NOT_REFERENCED":
                print(f"   ⚠️  PAYMENT_TYPE not referenced in query")
        else:
            business_results.append((query, expected, "ERROR"))
        time.sleep(0.5)  # Rate limiting
    
    # Creator synonym tests
    print("\n" + "=" * 80)
    print("CREATOR SYNONYM TESTS")
    print("-" * 80)
    
    creator_tests = [
        "Show payments for ambassadors",
        "List all influencer invoices",
        "Total payments to talent",
        "Show creator payments",
        "List content creator amounts",
        "Show payments for ambassador Jordan Kahana",
        "List influencer Katie Reardon invoices",
        "Show Agency Mode ambassador payments",
        "List Direct Mode influencer totals",
    ]
    
    creator_results = []
    for query in creator_tests:
        success, sql, error = test_payment_query(query)
        if success and sql:
            sql_upper = sql.upper()
            if "CREATOR" in sql_upper or "STRIPE_CONNECTED_ACCOUNT" in sql_upper:
                creator_results.append((query, "FOUND"))
                print(f"   ✅ References creator fields")
            else:
                creator_results.append((query, "NOT_FOUND"))
                print(f"   ❌ No creator field references")
        else:
            creator_results.append((query, "ERROR"))
        time.sleep(0.5)
    
    # Complex queries
    print("\n" + "=" * 80)
    print("COMPLEX QUERY TESTS")
    print("-" * 80)
    
    complex_tests = [
        "Compare total payment volume between labs and self-serve models for 2025",
        "Show top 5 creators by payment amount in Agency Mode",
        "List unpaid invoices for Direct Mode customers",
        "Total labs payments for Jordan Kahana",
        "Show self-serve ambassador payments this month",
    ]
    
    for query in complex_tests:
        success, sql, error = test_payment_query(query)
        if success:
            print(f"   ✅ Query executed successfully")
        time.sleep(0.5)
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("-" * 80)
    
    # Business model results
    correct_business = sum(1 for _, _, result in business_results if result == "CORRECT")
    print(f"\nBusiness Model Synonyms: {correct_business}/{len(business_results)} correct")
    for query, expected, result in business_results:
        if result != "CORRECT":
            print(f"  ❌ '{query}' - {result}")
    
    # Creator synonym results
    found_creators = sum(1 for _, result in creator_results if result == "FOUND")
    print(f"\nCreator Synonyms: {found_creators}/{len(creator_results)} found creator references")
    for query, result in creator_results:
        if result != "FOUND":
            print(f"  ❌ '{query}' - {result}")
    
    print("\n" + "=" * 80)
    print("✅ All queries sent through production MCP interface")
    print("📊 Check PF.BI.AI_USER_ACTIVITY_LOG for logged entries")
    print(f"   Look for entries after {datetime.now().isoformat()}")
    print("=" * 80)

if __name__ == "__main__":
    main()