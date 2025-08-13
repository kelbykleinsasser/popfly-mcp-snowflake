#!/usr/bin/env python3
"""
Test script to check how PAKA queries are handled
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

async def test_paka_query():
    from tools.payment_tools import query_payments_handler
    import json
    
    query = "show me the PAKA creator payment totals by campaign"
    
    arguments = {
        "query": query,
        "max_rows": 100
    }
    
    print(f"Testing query: {query}")
    print("-" * 80)
    
    result = await query_payments_handler(
        arguments, 
        bearer_token="test_token",
        request_id="test_paka_123"
    )
    
    if result and hasattr(result[0], 'text'):
        text = result[0].text
        
        # Extract SQL from the response
        if "Generated SQL:" in text:
            sql_start = text.find("Generated SQL:") + len("Generated SQL: `")
            sql_end = text.find("`", sql_start)
            if sql_end > sql_start:
                generated_sql = text[sql_start:sql_end]
                print(f"\nGenerated SQL:\n{generated_sql}\n")
                
                # Check what kind of matching is used
                if "LIKE '%PAKA%'" in generated_sql.upper():
                    print("❌ PROBLEM: Using LIKE '%PAKA%' which will match Alpaka")
                elif "= 'PAKA'" in generated_sql.upper():
                    print("✅ GOOD: Using exact match = 'PAKA'")
                elif "REGEXP" in generated_sql.upper() or "RLIKE" in generated_sql.upper():
                    print("✅ GOOD: Using regex for word boundaries")
                else:
                    print("⚠️  CHECK: Unknown matching pattern")
        
        # Parse JSON results
        json_end = text.find("\n\n**")
        if json_end == -1:
            json_end = len(text)
        json_str = text[:json_end]
        
        try:
            results = json.loads(json_str)
            print(f"\nResults ({len(results)} rows):")
            
            # Check if Alpaka appears in results
            has_alpaka = False
            has_paka = False
            
            for row in results:
                if 'COMPANY_NAME' in row:
                    if 'ALPAKA' in str(row['COMPANY_NAME']).upper():
                        has_alpaka = True
                    if row['COMPANY_NAME'] == 'PAKA':
                        has_paka = True
                    print(f"  Company: {row['COMPANY_NAME']}, Campaign: {row.get('CAMPAIGN_NAME', 'N/A')}")
            
            print(f"\nValidation:")
            if has_alpaka:
                print("❌ PROBLEM: Results include ALPAKA (should only be PAKA)")
            if has_paka:
                print("✅ Results include PAKA")
            if not has_alpaka and has_paka:
                print("✅ SUCCESS: Only PAKA results returned")
                
        except json.JSONDecodeError as e:
            print(f"Could not parse results: {e}")

if __name__ == "__main__":
    asyncio.run(test_paka_query())