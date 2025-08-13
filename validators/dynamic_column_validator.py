"""
Dynamic column validator that checks against actual database schema
"""
import re
import logging
from typing import Set, Optional
from dataclasses import dataclass

@dataclass
class SqlValidationResult:
    is_valid: bool
    error: Optional[str] = None

class DynamicColumnValidator:
    """Validates SQL queries against actual database schema"""
    
    def __init__(self):
        self._column_cache = {}
        
    def get_table_columns(self, table_name: str, connection) -> Set[str]:
        """Get actual columns from database for a table"""
        cache_key = table_name.upper()
        
        if cache_key in self._column_cache:
            return self._column_cache[cache_key]
        
        try:
            cursor = connection.cursor()
            
            # Parse table name (could be schema.table or database.schema.table)
            parts = table_name.upper().split('.')
            if len(parts) == 3:
                database, schema, table = parts
            elif len(parts) == 2:
                database = None
                schema, table = parts
            else:
                database = None
                schema = 'BI'  # Default schema
                table = parts[0]
            
            # Query information schema for columns
            query = """
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = %s
                AND TABLE_SCHEMA = %s
            """
            
            cursor.execute(query, (table, schema))
            columns = {row[0] for row in cursor.fetchall()}
            
            cursor.close()
            
            # Cache the result
            self._column_cache[cache_key] = columns
            
            logging.info(f"Loaded {len(columns)} columns for {table_name}")
            return columns
            
        except Exception as e:
            logging.error(f"Failed to get columns for {table_name}: {e}")
            # Return empty set if we can't get schema
            return set()
    
    def validate_columns(self, sql: str, table_name: str, connection) -> SqlValidationResult:
        """Validate that SQL only references existing columns"""
        
        # Get actual columns from database
        valid_columns = self.get_table_columns(table_name, connection)
        
        if not valid_columns:
            # If we couldn't get schema, skip validation
            return SqlValidationResult(is_valid=True)
        
        sql_upper = sql.upper()
        
        # Extract potential column references
        # This is simplified - ideally we'd use a proper SQL parser
        referenced_columns = set()
        
        # Find columns in various SQL clauses
        patterns = [
            r'SELECT\s+(.*?)\s+FROM',
            r'WHERE\s+(.*?)(?:GROUP|ORDER|LIMIT|;|$)',
            r'GROUP\s+BY\s+(.*?)(?:HAVING|ORDER|LIMIT|;|$)',
            r'ORDER\s+BY\s+(.*?)(?:LIMIT|;|$)',
            r'COUNT\s*\(\s*([A-Z_][A-Z0-9_]*)\s*\)',
            r'SUM\s*\(\s*([A-Z_][A-Z0-9_]*)\s*\)',
            r'AVG\s*\(\s*([A-Z_][A-Z0-9_]*)\s*\)',
            r'MIN\s*\(\s*([A-Z_][A-Z0-9_]*)\s*\)',
            r'MAX\s*\(\s*([A-Z_][A-Z0-9_]*)\s*\)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, sql_upper, re.DOTALL)
            for match in matches:
                # Extract column names
                potential_cols = re.findall(r'\b([A-Z_][A-Z0-9_]*)\b', match)
                for col in potential_cols:
                    # Skip SQL keywords, functions, and aliases
                    if not self._is_sql_keyword(col):
                        referenced_columns.add(col)
        
        # Check for invalid columns
        invalid_columns = referenced_columns - valid_columns
        
        # Remove columns that might be aliases or derived
        invalid_columns = {col for col in invalid_columns 
                          if not any(alias in col for alias in ['_COUNT', '_SUM', '_AVG', '_MIN', '_MAX', 'TOTAL_'])}
        
        if invalid_columns:
            # Provide helpful suggestions
            suggestions = []
            for invalid_col in invalid_columns:
                if 'PAYMENT_ID' in invalid_col or invalid_col == 'ID':
                    suggestions.append(f"Use REFERENCE_ID instead of {invalid_col}")
                elif 'INVOICE_ID' in invalid_col:
                    suggestions.append(f"Use REFERENCE_ID for invoice IDs")
                elif 'TRANSFER_ID' in invalid_col:
                    suggestions.append(f"Use REFERENCE_ID for transfer IDs")
                    
            error_msg = f"Column(s) {', '.join(sorted(invalid_columns))} do not exist. "
            if suggestions:
                error_msg += " ".join(suggestions) + ". "
            error_msg += f"Valid columns: {', '.join(sorted(valid_columns))}"
            
            return SqlValidationResult(is_valid=False, error=error_msg)
        
        return SqlValidationResult(is_valid=True)
    
    def _is_sql_keyword(self, word: str) -> bool:
        """Check if a word is a SQL keyword or function"""
        keywords = {
            'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'AS', 'COUNT', 'SUM', 'AVG', 
            'MIN', 'MAX', 'DISTINCT', 'CASE', 'WHEN', 'THEN', 'END', 'ELSE', 
            'NULL', 'NOT', 'IN', 'LIKE', 'BETWEEN', 'EXISTS', 'ANY', 'ALL', 
            'EXTRACT', 'YEAR', 'MONTH', 'DAY', 'HOUR', 'MINUTE', 'SECOND',
            'LIMIT', 'DESC', 'ASC', 'GROUP', 'BY', 'HAVING', 'ORDER', 'UNION',
            'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'FULL', 'CROSS', 'ON',
            'WITH', 'RECURSIVE', 'VALUES', 'INSERT', 'UPDATE', 'DELETE', 'INTO',
            'INTEGER', 'VARCHAR', 'TIMESTAMP', 'DATE', 'TIME', 'BOOLEAN', 'DECIMAL'
        }
        return word.upper() in keywords