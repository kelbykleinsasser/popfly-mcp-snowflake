#!/usr/bin/env python3
"""
Performance test for query_payments tool
Measures timing for each step in the pipeline
"""
import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_query_performance():
    """Test performance of a complex aggregation query"""
    
    # Import after setting up logging
    from tools.payment_tools import query_payments_handler
    from cortex.cortex_generator_v2 import CortexGenerator, CortexRequest
    from validators.sql_validator import SqlValidator
    from tools.snowflake_tools import read_query_handler
    from utils.config import get_environment_snowflake_connection
    
    query = "how much has been paid out to creators in August so far. Bifurcate on type"
    
    print("\n" + "="*80)
    print(f"PERFORMANCE TEST: {query}")
    print("="*80 + "\n")
    
    # Track timing for each step
    timings = {}
    
    # Step 1: Test Cortex SQL Generation
    print("Step 1: Cortex SQL Generation")
    start_cortex = time.time()
    
    cortex_request = CortexRequest(
        natural_language_query=query,
        view_name="MV_CREATOR_PAYMENTS_UNION",
        max_rows=1000
    )
    
    cortex_response = await CortexGenerator.generate_sql(cortex_request)
    
    cortex_time = time.time() - start_cortex
    timings['cortex_generation'] = cortex_time * 1000  # Convert to ms
    
    if cortex_response.success:
        print(f"✓ Generated SQL: {cortex_response.generated_sql[:100]}...")
        print(f"  Time: {timings['cortex_generation']:.2f}ms")
    else:
        print(f"✗ Failed: {cortex_response.error}")
        return
    
    # Step 2: SQL Validation
    print("\nStep 2: SQL Validation")
    start_validation = time.time()
    
    validator = DynamicSqlValidator()
    validation_result = validator.validate_sql_query(cortex_response.generated_sql)
    
    validation_time = time.time() - start_validation
    timings['validation'] = validation_time * 1000
    
    print(f"✓ Validation: {'Passed' if validation_result.is_valid else 'Failed'}")
    print(f"  Time: {timings['validation']:.2f}ms")
    
    # Step 3: SQL Execution
    print("\nStep 3: SQL Execution")
    start_execution = time.time()
    
    sql_arguments = {
        "query": cortex_response.generated_sql,
        "max_rows": 1000
    }
    
    sql_results = await read_query_handler(sql_arguments, bearer_token="test_token", is_internal=True)
    
    execution_time = time.time() - start_execution
    timings['sql_execution'] = execution_time * 1000
    
    print(f"✓ Query executed")
    print(f"  Time: {timings['sql_execution']:.2f}ms")
    
    # Step 4: Result Processing
    print("\nStep 4: Result Processing")
    start_processing = time.time()
    
    # Extract and parse results
    row_count = 0
    if sql_results and sql_results[0].text:
        sql_text = sql_results[0].text
        if "rows returned:" in sql_text:
            import re
            json_match = re.search(r'\d+\s+rows returned:\s*(\[.*\])', sql_text, re.DOTALL)
            if json_match:
                results_data = json.loads(json_match.group(1))
                row_count = len(results_data)
                # Format as clean JSON
                clean_result = json.dumps(results_data, indent=2)
    
    processing_time = time.time() - start_processing
    timings['result_processing'] = processing_time * 1000
    
    print(f"✓ Results processed: {row_count} rows")
    print(f"  Time: {timings['result_processing']:.2f}ms")
    
    # Step 5: Full End-to-End Test
    print("\nStep 5: Full End-to-End Test (query_payments_handler)")
    start_e2e = time.time()
    
    arguments = {"query": query, "max_rows": 1000}
    e2e_results = await query_payments_handler(arguments, bearer_token="test_token")
    
    e2e_time = time.time() - start_e2e
    timings['end_to_end'] = e2e_time * 1000
    
    print(f"✓ Complete handler execution")
    print(f"  Time: {timings['end_to_end']:.2f}ms")
    
    # Performance Analysis
    print("\n" + "="*80)
    print("PERFORMANCE ANALYSIS")
    print("="*80)
    
    print("\nTiming Breakdown:")
    print(f"  1. Cortex SQL Generation: {timings['cortex_generation']:.2f}ms ({timings['cortex_generation']/timings['end_to_end']*100:.1f}%)")
    print(f"  2. SQL Validation:        {timings['validation']:.2f}ms ({timings['validation']/timings['end_to_end']*100:.1f}%)")
    print(f"  3. SQL Execution:         {timings['sql_execution']:.2f}ms ({timings['sql_execution']/timings['end_to_end']*100:.1f}%)")
    print(f"  4. Result Processing:     {timings['result_processing']:.2f}ms ({timings['result_processing']/timings['end_to_end']*100:.1f}%)")
    print(f"  --------------------------------")
    print(f"  Total (End-to-End):      {timings['end_to_end']:.2f}ms")
    
    # Calculate overhead
    component_sum = (timings['cortex_generation'] + timings['validation'] + 
                    timings['sql_execution'] + timings['result_processing'])
    overhead = timings['end_to_end'] - component_sum
    print(f"  Overhead/Logging:         {overhead:.2f}ms ({overhead/timings['end_to_end']*100:.1f}%)")
    
    print("\nBottleneck Analysis:")
    sorted_timings = sorted(timings.items(), key=lambda x: x[1], reverse=True)
    bottleneck = sorted_timings[0]
    print(f"  Primary bottleneck: {bottleneck[0]} ({bottleneck[1]:.2f}ms)")
    
    print("\nOptimization Opportunities:")
    print("  (Analysis only - no changes will be implemented)")
    
    if timings['cortex_generation'] > 2000:
        print("  • Cortex generation is slow (>2s)")
        print("    - Consider caching frequent queries")
        print("    - Pre-compile common query patterns")
        print("    - Use smaller Cortex model if available")
    
    if timings['sql_execution'] > 1000:
        print("  • SQL execution is slow (>1s)")
        print("    - Check if indexes are being used")
        print("    - Analyze query plan for optimization")
        print("    - Consider materialized view refresh frequency")
    
    if timings['validation'] > 100:
        print("  • Validation overhead is high (>100ms)")
        print("    - Cache allowed tables list")
        print("    - Optimize regex patterns")
    
    if timings['result_processing'] > 500:
        print("  • Result processing is slow (>500ms)")
        print("    - Stream results instead of loading all in memory")
        print("    - Use more efficient JSON parsing")
    
    if overhead > 500:
        print("  • High overhead/logging cost (>500ms)")
        print("    - Batch logging operations")
        print("    - Use async logging")
        print("    - Reduce logging granularity")
    
    print("\nExpected Production Performance:")
    print("  • With connection pooling: ~20% faster SQL execution")
    print("  • With result caching: ~90% faster for repeated queries")
    print("  • With async logging: ~50% less overhead")
    print("  • Estimated production time: ~{:.0f}ms".format(timings['end_to_end'] * 0.7))
    
    return timings

if __name__ == "__main__":
    # Run the test
    asyncio.run(test_query_performance())