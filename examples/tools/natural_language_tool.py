class QueryCache:
    """Simple cache implementation for the example"""
    def __init__(self, ttl=300):
        self.cache = {}
        self.ttl = ttl
    
    def get(self, key):
        return self.cache.get(key)
    
    def set(self, key, value):
        self.cache[key] = value

class NaturalLanguageQueryTool:
    def __init__(self, connection, view_name: str):
        self.connection = connection
        self.view_name = view_name
        self.cortex_generator = CortexSQLGenerator(connection)
        self.validator = CortexSQLValidator(self._load_view_constraints())
        self.cache = QueryCache(ttl=300)  # 5 minute cache
        
        # Tool metadata for Open WebUI registration
        self.description = f"Query {view_name} using natural language. Handles all types of queries including filtering, aggregation, and sorting."
        self.input_schema = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query"
                },
                "include_sql": {
                    "type": "boolean",
                    "description": "Include generated SQL in response",
                    "default": True
                },
                "max_rows": {
                    "type": "integer",
                    "description": "Maximum rows to return",
                    "default": 1000
                }
            },
            "required": ["query"]
        }
    
    async def execute(self, parameters: dict) -> dict:
        """Execute natural language query using Cortex"""
        query = parameters['query']
        
        # Check cache first
        cache_key = f"{self.view_name}:{query}"
        if cached_sql := self.cache.get(cache_key):
            sql = cached_sql
        else:
            # Generate SQL using Cortex
            sql = await self.cortex_generator.generate_sql(
                query, 
                self._get_view_config()
            )
            
            # Validate generated SQL
            is_valid, message = self.validator.validate_generated_sql(sql)
            if not is_valid:
                raise ValueError(f"Generated SQL failed validation: {message}")
            
            # Cache successful generation
            self.cache.set(cache_key, sql)
        
        # Execute query
        results = self._execute_sql(sql, parameters.get('max_rows', 1000))
        
        # Log activity
        self._log_activity(query, sql, len(results))
        
        # Return results
        response = {"data": results, "row_count": len(results)}
        if parameters.get('include_sql', True):
            response['generated_sql'] = sql
            
        return response
    
    def _load_view_constraints(self):
        """Load view constraints from database"""
        # Implementation to load constraints
        return {
            'view_name': self.view_name,
            'columns': ['column1', 'column2']  # Example
        }
    
    def _get_view_config(self):
        """Get view configuration"""
        # Implementation to get view config
        return {
            'view_name': self.view_name,
            'columns': ['column1', 'column2'],
            'column_descriptions': {
                'column1': 'Description of column1',
                'column2': 'Description of column2'
            }
        }
    
    def _execute_sql(self, sql: str, max_rows: int):
        """Execute SQL and return results"""
        # Implementation to execute SQL
        return []
    
    def _log_activity(self, query: str, sql: str, row_count: int):
        """Log activity for audit trail"""
        # Implementation for logging
        pass
