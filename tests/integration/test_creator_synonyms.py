#!/usr/bin/env python3
"""
Test creator synonym variations to ensure they reference CREATOR_NAME correctly
"""
import asyncio
from cortex.cortex_generator_v2 import CortexGenerator, CortexRequest

# Test cases for creator synonyms
TEST_CASES = [
    # Test individual terms
    ("Show payments for ambassadors", "CREATOR"),
    ("List all influencer invoices", "CREATOR"),
    ("Total payments to talent", "CREATOR"),
    ("Show creator payments", "CREATOR"),
    ("List content creator amounts", "CREATOR"),
    
    # Test specific creator names
    ("Show payments for ambassador Jordan Kahana", "CREATOR_NAME"),
    ("List influencer Katie Reardon invoices", "CREATOR_NAME"),
    
    # Combined with business model
    ("Show Agency Mode ambassador payments", ["PAYMENT_TYPE", "CREATOR"]),
    ("List Direct Mode influencer totals", ["PAYMENT_TYPE", "CREATOR"]),
]

async def test_creator_reference(query: str, expected):
    """Test if creator synonyms are properly understood"""
    request = CortexRequest(
        natural_language_query=query,
        view_name='MV_CREATOR_PAYMENTS_UNION',
        max_rows=100
    )
    
    response = await CortexGenerator.generate_sql(request)
    
    if not response.success or not response.generated_sql:
        return f"❌ FAILED to generate SQL for: {query}"
    
    sql = response.generated_sql.upper()
    
    # Check what the SQL references
    if isinstance(expected, list):
        # Multiple expected references
        found = []
        for exp in expected:
            if exp in sql or f"{exp}_NAME" in sql or f"STRIPE_CONNECTED_ACCOUNT" in sql:
                found.append(exp)
        if len(found) == len(expected):
            return f"✅ PASS: '{query}' → references {', '.join(found)}"
        else:
            return f"⚠️  PARTIAL: '{query}' → found {found} (expected {expected})"
    else:
        # Single expected reference
        if "CREATOR_NAME" in sql or "STRIPE_CONNECTED_ACCOUNT" in sql:
            return f"✅ PASS: '{query}' → references creator fields"
        elif expected in sql:
            return f"✅ PASS: '{query}' → references {expected}"
        else:
            return f"❌ FAIL: '{query}' → doesn't reference creator fields"

async def main():
    print("Testing Creator Synonym Translations...")
    print("=" * 60)
    
    results = []
    failures = []
    
    for query, expected in TEST_CASES:
        result = await test_creator_reference(query, expected)
        print(result)
        results.append(result)
        
        if "FAIL" in result:
            failures.append((query, expected, result))
    
    print("\n" + "=" * 60)
    passed = len([r for r in results if '✅' in r])
    print(f"Results: {passed}/{len(TEST_CASES)} passed")
    
    if failures:
        print(f"\n❌ {len(failures)} failures:")
        for query, expected, result in failures:
            print(f"  - {query}")
    else:
        print("\n🎉 All creator synonym translations working correctly!")
    
    # Show actual SQL for a few examples
    print("\n" + "=" * 60)
    print("Example SQL generated:")
    example_queries = [
        "Show payments for ambassadors",
        "List all influencer invoices",
        "Show payments for ambassador Jordan Kahana"
    ]
    
    for query in example_queries:
        request = CortexRequest(
            natural_language_query=query,
            view_name='MV_CREATOR_PAYMENTS_UNION',
            max_rows=100
        )
        response = await CortexGenerator.generate_sql(request)
        if response.success:
            print(f"\n{query}:")
            print(f"  → {response.generated_sql}")

if __name__ == "__main__":
    asyncio.run(main())