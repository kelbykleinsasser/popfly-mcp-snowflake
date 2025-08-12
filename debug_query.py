#!/usr/bin/env python3
"""
Debug why specific queries aren't returning results
"""
import asyncio
import json
from cortex.cortex_generator_v2 import CortexGenerator, CortexRequest
from utils.cortex_search import CortexSearchClient
from config.settings import settings
from utils.connection_pool import get_pooled_connection

async def debug_query():
    """Debug the specific query that's not working"""
    
    query = "Compare total creator payment volume between labs and direct business models - show total payment amounts, payment counts, and average payments grouped by business model (labs vs direct)"
    
    print("=" * 60)
    print("DEBUGGING QUERY")
    print("=" * 60)
    print(f"Query: {query}\n")
    
    # 1. Check what context is being built
    print("1. CONTEXT RETRIEVAL")
    print("-" * 40)
    context = CortexSearchClient.build_minimal_context(query, "MV_CREATOR_PAYMENTS_UNION")
    print(f"Context built ({len(context)} chars):")
    print(context)
    print()
    
    # 2. Generate SQL
    print("2. SQL GENERATION")
    print("-" * 40)
    request = CortexRequest(
        natural_language_query=query,
        view_name="MV_CREATOR_PAYMENTS_UNION",
        max_rows=1000
    )
    
    response = await CortexGenerator.generate_sql(request)
    print(f"Success: {response.success}")
    print(f"Generated SQL:\n{response.generated_sql}")
    
    if response.error:
        print(f"Error: {response.error}")
    
    # 3. Test the SQL directly
    if response.success and response.generated_sql:
        print("\n3. EXECUTING SQL")
        print("-" * 40)
        
        try:
            with get_pooled_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(response.generated_sql)
                results = cursor.fetchall()
                
                print(f"Rows returned: {len(results)}")
                
                if results:
                    # Show first few results
                    print("\nFirst 5 rows:")
                    for i, row in enumerate(results[:5]):
                        print(f"  {i+1}: {row}")
                else:
                    print("No results returned!")
                    
                    # Let's check what columns exist
                    print("\n4. CHECKING AVAILABLE DATA")
                    print("-" * 40)
                    
                    # Check distinct values in PAYMENT_TYPE
                    cursor.execute("SELECT DISTINCT PAYMENT_TYPE, COUNT(*) as cnt FROM MV_CREATOR_PAYMENTS_UNION GROUP BY PAYMENT_TYPE")
                    payment_types = cursor.fetchall()
                    print("Available PAYMENT_TYPE values:")
                    for row in payment_types:
                        print(f"  - {row[0]}: {row[1]} records")
                    
                    # Check if there's a business model column
                    cursor.execute("SELECT * FROM MV_CREATOR_PAYMENTS_UNION LIMIT 1")
                    sample = cursor.fetchone()
                    if sample:
                        col_names = [desc[0] for desc in cursor.description]
                        print(f"\nAvailable columns: {col_names}")
                        
                        # Look for business model related columns
                        business_cols = [col for col in col_names if 'BUSINESS' in col.upper() or 'MODEL' in col.upper() or 'TYPE' in col.upper()]
                        print(f"Business-related columns: {business_cols}")
                
                cursor.close()
                
        except Exception as e:
            print(f"SQL execution error: {e}")
    
    # 5. Check schema metadata
    print("\n5. SCHEMA METADATA CHECK")
    print("-" * 40)
    
    with get_pooled_connection() as conn:
        cursor = conn.cursor()
        
        # Check what metadata we have about business model
        cursor.execute("""
            SELECT COLUMN_NAME, BUSINESS_MEANING, KEYWORDS, EXAMPLES
            FROM AI_SCHEMA_METADATA
            WHERE TABLE_NAME = 'MV_CREATOR_PAYMENTS_UNION'
            AND (
                LOWER(COLUMN_NAME) LIKE '%business%' 
                OR LOWER(COLUMN_NAME) LIKE '%model%'
                OR LOWER(COLUMN_NAME) LIKE '%type%'
                OR LOWER(COLUMN_NAME) LIKE '%mode%'
                OR LOWER(BUSINESS_MEANING) LIKE '%business%'
                OR LOWER(BUSINESS_MEANING) LIKE '%labs%'
                OR LOWER(BUSINESS_MEANING) LIKE '%direct%'
            )
        """)
        
        metadata = cursor.fetchall()
        print("Relevant metadata entries:")
        for row in metadata:
            print(f"  Column: {row[0]}")
            print(f"    Meaning: {row[1]}")
            print(f"    Keywords: {row[2]}")
            print(f"    Examples: {row[3]}")
            print()
        
        cursor.close()

if __name__ == "__main__":
    asyncio.run(debug_query())