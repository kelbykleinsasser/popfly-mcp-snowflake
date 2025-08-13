#!/usr/bin/env python3
"""
Test Cortex Search integration and performance improvements
"""
import asyncio
import time
import json
from cortex.cortex_generator_v2 import CortexGenerator, CortexRequest
from utils.cortex_search import CortexSearchClient
from config.settings import settings

async def test_search_services():
    """Test that Cortex Search services are working"""
    print("=" * 60)
    print("Testing Cortex Search Services")
    print("=" * 60)
    
    query = "how much has been paid out to creators in August so far. Bifurcate on type"
    view_name = "MV_CREATOR_PAYMENTS_UNION"
    
    print(f"\nTest Query: {query}")
    print("-" * 40)
    
    # Test schema search
    print("\n1. Testing Schema Search...")
    schema_results = CortexSearchClient.search_schema_context(query, view_name)
    print(f"Found {len(schema_results)} relevant columns")
    for result in schema_results[:3]:
        print(f"  - {result.data['column_name']}: {result.data['business_meaning'][:50]}...")
    
    # Test business context search
    print("\n2. Testing Business Context Search...")
    business_results = CortexSearchClient.search_business_context(query)
    print(f"Found {len(business_results)} business rules")
    for result in business_results:
        print(f"  - {result.data.get('title', 'N/A')}: {result.data.get('description', '')[:50]}...")
    
    # Test constraints lookup
    print("\n3. Testing View Constraints...")
    constraints = CortexSearchClient.get_view_constraints(view_name)
    if constraints:
        print(f"  - Found constraints for {view_name}")
        print(f"  - Allowed operations: {constraints.data.get('allowed_operations', '')[:50]}...")
    
    # Test minimal context building
    print("\n4. Building Minimal Context...")
    context = CortexSearchClient.build_minimal_context(query, view_name)
    print(f"Context size: {len(context)} chars (was ~5000)")
    print(f"Reduction: {(1 - len(context)/5000) * 100:.1f}%")
    print("\nContext preview:")
    print("-" * 40)
    print(context[:500] + "..." if len(context) > 500 else context)
    
    return True

async def compare_performance():
    """Compare traditional vs search-based SQL generation"""
    print("\n" + "=" * 60)
    print("Performance Comparison: Traditional vs Cortex Search")
    print("=" * 60)
    
    test_queries = [
        "how much has been paid out to creators in August so far. Bifurcate on type",
        "show total payments by status for this month",
        "what are the top 10 creators by payment amount"
    ]
    
    for query_text in test_queries:
        print(f"\nQuery: {query_text[:50]}...")
        print("-" * 40)
        
        request = CortexRequest(
            natural_language_query=query_text,
            view_name="MV_CREATOR_PAYMENTS_UNION",
            max_rows=1000
        )
        
        # Test with traditional approach
        settings.cortex_use_search = False
        start = time.time()
        response1 = await CortexGenerator.generate_sql(request)
        time_traditional = (time.time() - start) * 1000
        
        # Test with search approach
        settings.cortex_use_search = True
        start = time.time()
        response2 = await CortexGenerator.generate_sql(request)
        time_search = (time.time() - start) * 1000
        
        # Compare results
        print(f"Traditional: {time_traditional:.0f}ms | Prompt: {response1.prompt_char_count or 'N/A'} chars")
        print(f"Search-based: {time_search:.0f}ms | Prompt: {response2.prompt_char_count or 'N/A'} chars")
        
        improvement = time_traditional - time_search
        if improvement > 0:
            print(f"✅ Search is {improvement:.0f}ms faster ({improvement/time_traditional*100:.1f}% improvement)")
        else:
            print(f"⚠️ Search is {abs(improvement):.0f}ms slower")
        
        if response1.success and response2.success:
            if response1.generated_sql == response2.generated_sql:
                print("✅ SQL output: IDENTICAL")
            else:
                print("⚠️ SQL output: DIFFERENT")
                print(f"   Traditional: {response1.generated_sql[:100]}...")
                print(f"   Search-based: {response2.generated_sql[:100]}...")

async def test_specific_query():
    """Test the specific slow query that was reported"""
    print("\n" + "=" * 60)
    print("Testing Specific Slow Query")
    print("=" * 60)
    
    query = "how much has been paid out to creators in August so far. Bifurcate on type"
    
    request = CortexRequest(
        natural_language_query=query,
        view_name="MV_CREATOR_PAYMENTS_UNION",
        max_rows=1000
    )
    
    # Ensure search is enabled
    settings.cortex_use_search = True
    
    print(f"\nQuery: {query}")
    print("-" * 40)
    
    start = time.time()
    response = await CortexGenerator.generate_sql(request)
    total_time = (time.time() - start) * 1000
    
    print(f"Total time: {total_time:.0f}ms")
    print(f"Prompt size: {response.prompt_char_count} chars")
    print(f"Success: {response.success}")
    
    if response.generated_sql:
        print(f"\nGenerated SQL:")
        print(response.generated_sql)
    
    if response.error:
        print(f"\nError: {response.error}")
    
    # Show improvement
    print(f"\n📊 Performance Summary:")
    print(f"  - Previous time: ~40,000ms (40 seconds)")
    print(f"  - Current time: {total_time:.0f}ms")
    print(f"  - Improvement: {(40000 - total_time)/40000 * 100:.1f}%")
    print(f"  - Prompt reduction: ~5000 → {response.prompt_char_count} chars")

if __name__ == "__main__":
    # Run all tests
    asyncio.run(test_search_services())
    asyncio.run(compare_performance())
    asyncio.run(test_specific_query())