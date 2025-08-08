import json
import asyncio

async def generate_sql_with_cortex(natural_language_query: str, view_context: dict, connection) -> str:
    """Use Snowflake Cortex to generate SQL from natural language"""
    
    prompt = f"""
    Generate a SQL query for the following request:
    "{natural_language_query}"
    
    Context:
    - Table: {view_context['view_name']}
    - Available columns: {', '.join(view_context['columns'])}
    - Column descriptions: {json.dumps(view_context['column_descriptions'])}
    
    Requirements:
    - Only use SELECT statements
    - Only query from {view_context['view_name']}
    - Include appropriate WHERE clauses based on the request
    - Add ORDER BY and LIMIT as appropriate
    - Do not use any JOINs, subqueries, or CTEs
    - Return only the SQL query, no explanations
    """
    
    # Call Cortex COMPLETE function
    query = f"""
    SELECT SNOWFLAKE.CORTEX.COMPLETE(
        'llama3.1-70b',  # or later model
        '{prompt}'
    ) as generated_sql
    """
    
    result = connection.execute(query).fetchone()
    return result['generated_sql']
