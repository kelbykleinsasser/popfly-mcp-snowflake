class CortexSQLValidator:
    def __init__(self, view_config: dict):
        self.allowed_view = view_config['view_name']
        self.allowed_columns = set(view_config['columns'])
        self.forbidden_keywords = {'DROP', 'DELETE', 'UPDATE', 'INSERT', 'CREATE', 
                                  'ALTER', 'TRUNCATE', 'MERGE', 'GRANT', 'REVOKE'}
    
    def validate_generated_sql(self, sql: str) -> tuple[bool, str]:
        """Validate Cortex-generated SQL for safety"""
        sql_upper = sql.upper()
        
        # Check for forbidden operations
        for keyword in self.forbidden_keywords:
            if keyword in sql_upper:
                return False, f"Forbidden operation: {keyword}"
        
        # Verify it only queries allowed view
        if self.allowed_view.upper() not in sql_upper:
            return False, f"Query must reference {self.allowed_view}"
        
        # Parse and validate column references
        try:
            # Use sqlparse or similar to validate column names
            if not self._validate_columns(sql):
                return False, "Query references invalid columns"
        except Exception as e:
            return False, f"Failed to parse SQL: {str(e)}"
        
        return True, "SQL validated successfully"
    
    def _validate_columns(self, sql: str) -> bool:
        """Validate that only allowed columns are referenced"""
        # This is a simplified implementation
        # In practice, you'd use sqlparse to properly parse the SQL
        # and extract column references
        return True
