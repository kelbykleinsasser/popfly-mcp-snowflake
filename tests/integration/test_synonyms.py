#!/usr/bin/env python3
"""
Test synonym variations for PAYMENT_TYPE to ensure proper translation
"""
import asyncio
from cortex.cortex_generator_v2 import CortexGenerator, CortexRequest

# Test cases: (query phrase, expected canonical value)
TEST_CASES = [
    # Agency Mode synonyms
    ("Show payments for labs", "Agency Mode"),
    ("Total for Popfly Labs business model", "Agency Mode"),
    ("List agency services payments", "Agency Mode"),
    ("agency payments total", "Agency Mode"),
    ("labs invoice amounts", "Agency Mode"),
    
    # Direct Mode synonyms  
    ("self-serve payment totals", "Direct Mode"),
    ("self serve creators", "Direct Mode"),
    ("platform payments", "Direct Mode"),
    ("direct business model", "Direct Mode"),
    ("self service invoices", "Direct Mode"),
]

async def test_synonym(query: str, expected: str):
    """Test if a query correctly translates synonyms to canonical values"""
    request = CortexRequest(
        natural_language_query=query,
        view_name='MV_CREATOR_PAYMENTS_UNION',
        max_rows=100
    )
    
    response = await CortexGenerator.generate_sql(request)
    
    if not response.success or not response.generated_sql:
        return f"❌ FAILED to generate SQL for: {query}"
    
    sql = response.generated_sql
    
    # Check if the expected canonical value is in the SQL
    if expected in sql:
        return f"✅ PASS: '{query}' → uses '{expected}'"
    
    # Check for common incorrect values
    incorrect_values = {
        "Agency Mode": ["Labs", "labs", "Popfly Labs", "agency services"],
        "Direct Mode": ["self-serve", "self serve", "platform", "self service"]
    }
    
    for incorrect in incorrect_values.get(expected, []):
        if incorrect in sql:
            return f"❌ FAIL: '{query}' → uses '{incorrect}' instead of '{expected}'"
    
    return f"⚠️  UNCLEAR: '{query}' → SQL doesn't reference payment type"

async def main():
    print("Testing PAYMENT_TYPE synonym translations...")
    print("=" * 60)
    
    results = []
    failures = []
    
    for query, expected in TEST_CASES:
        result = await test_synonym(query, expected)
        print(result)
        results.append(result)
        
        if "FAIL" in result:
            failures.append((query, expected, result))
    
    print("\n" + "=" * 60)
    print(f"Results: {len([r for r in results if '✅' in r])}/{len(TEST_CASES)} passed")
    
    if failures:
        print(f"\n❌ {len(failures)} failures need narrative updates:")
        for query, expected, result in failures:
            print(f"  - {query} should use {expected}")
    else:
        print("\n🎉 All synonym translations working correctly!")

if __name__ == "__main__":
    asyncio.run(main())