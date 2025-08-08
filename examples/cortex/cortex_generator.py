import json
from typing import Dict, Optional
import snowflake.connector

class Config:
    """Simple config class for the example"""
    def __init__(self):
        self.cortex_model = 'llama3.1-70b'

class CortexSQLGenerator:
    def __init__(self, connection: snowflake.connector.SnowflakeConnection):
        self.connection = connection
        self.config = Config()
        self.model = self.config.cortex_model or 'llama3.1-70b'
    
    async def generate_sql(self, 
                          natural_language_query: str,
                          view_config: Dict,
                          context: Optional[Dict] = None) -> str:
        """Generate SQL using Snowflake Cortex COMPLETE function"""
        
        # Build comprehensive prompt
        prompt = self._build_prompt(natural_language_query, view_config, context)
        
        # Call Cortex
        cortex_query = f"""
        SELECT SNOWFLAKE.CORTEX.COMPLETE(
            '{self.model}',
            '{self._escape_prompt(prompt)}'
        ) as generated_sql
        """
        
        cursor = self.connection.cursor()
        try:
            cursor.execute(cortex_query)
            result = cursor.fetchone()
            
            # Log Cortex usage
            self._log_cortex_usage(natural_language_query, result[0])
            
            return self._extract_sql(result[0])
            
        finally:
            cursor.close()
    
    def _build_prompt(self, query: str, view_config: Dict, context: Dict) -> str:
        """Build a comprehensive prompt for Cortex"""
        return f"""
        You are a SQL expert. Generate a SELECT query for this request:
        "{query}"
        
        STRICT REQUIREMENTS:
        1. ONLY use {view_config['view_name']} table
        2. ONLY use these columns: {', '.join(view_config['columns'])}
        3. ONLY use SELECT, WHERE, GROUP BY, ORDER BY, LIMIT clauses
        4. NO subqueries, NO joins, NO CTEs, NO unions
        5. Always include a LIMIT clause (max 10000)
        6. Return ONLY the SQL query - no explanations or markdown
        
        Column Information:
        {json.dumps(view_config['column_descriptions'], indent=2)}
        
        Business Context:
        {context.get('business_rules', 'Standard payment data queries')}
        
        Example of expected format:
        SELECT column1, column2 
        FROM {view_config['view_name']} 
        WHERE condition 
        ORDER BY column1 DESC 
        LIMIT 1000
        """
    
    def _escape_prompt(self, prompt: str) -> str:
        """Escape prompt for SQL string"""
        return prompt.replace("'", "''")
    
    def _extract_sql(self, cortex_result: str) -> str:
        """Extract SQL from Cortex result"""
        # Implementation depends on Cortex response format
        return cortex_result
    
    def _log_cortex_usage(self, query: str, result: str):
        """Log Cortex usage for monitoring"""
        # Implementation for logging
        pass
