#!/usr/bin/env python3
"""
Test direct call to query_payments_handler locally
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

async def test_direct():
    from tools.payment_tools import query_payments_handler
    
    arguments = {
        "query": "Total Agency Mode payments this month",
        "max_rows": 10
    }
    
    print("Testing direct call to query_payments_handler...")
    print(f"Query: {arguments['query']}")
    print("-" * 80)
    
    result = await query_payments_handler(
        arguments, 
        bearer_token="test_token",
        request_id="test_request_123"
    )
    
    print(f"Result type: {type(result)}")
    if result:
        print(f"Result length: {len(result)}")
        if hasattr(result[0], 'text'):
            text = result[0].text
            print(f"Text length: {len(text)}")
            print(f"First 200 chars: {text[:200]}")
            
            # Check for temporal markers
            if "Time Period:" in text or "August 2025" in text:
                print("\n✅ SUCCESS: Temporal context found!")
            else:
                print("\n⚠️  WARNING: No temporal context found")
                
            if "Generated SQL:" in text:
                print("✅ SUCCESS: SQL included")
            else:
                print("⚠️  WARNING: SQL not included")
                
            print(f"\nFull text:\n{text}")

if __name__ == "__main__":
    asyncio.run(test_direct())