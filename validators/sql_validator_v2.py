"""
Dynamic SQL Validator that loads allowed tables from database.
No more hardcoded table lists - single source of truth in database.
"""
import re
import logging
from typing import Dict, List, Set, Optional
from pydantic import BaseModel
from cortex.view_constraints_loader import ViewConstraintsLoader

class SqlValidationResult(BaseModel):
    is_valid: bool
    error: Optional[str] = None
    warnings: List[str] = []

class DynamicSqlValidator:
    """SQL validation system with dynamic table loading from database"""
    
    # These patterns are still hardcoded as they're security rules, not metadata
    DANGEROUS_PATTERNS = [
        r'DROP\s+TABLE',
        r'DELETE\s+FROM',
        r'TRUNCATE\s+TABLE',
        r'ALTER\s+TABLE',
        r'CREATE\s+TABLE',
        r'INSERT\s+INTO',
        r'UPDATE\s+.*SET',
        r'GRANT\s+',
        r'REVOKE\s+',
        r'EXEC\s+',
        r'EXECUTE\s+',
        r'xp_\w+',
        r'sp_\w+',
        r';\s*DROP',
        r';\s*DELETE',
        r'UNION\s+.*SELECT.*--',
        r'1\s*=\s*1',
        r'\'.*OR.*\'.*=.*\'',
    ]
    
    READ_ONLY_KEYWORDS = ['SELECT', 'SHOW', 'DESCRIBE', 'EXPLAIN', 'WITH']
    
    def __init__(self):
        """Initialize validator and load allowed tables from database"""
        self._allowed_tables: Optional[Set[str]] = None
        self._load_allowed_tables()
    
    def _load_allowed_tables(self) -> None:
        """Load allowed tables from database on initialization"""
        try:
            tables = ViewConstraintsLoader.get_allowed_tables()
            self._allowed_tables = set(table.upper() for table in tables)
            logging.info(f"Loaded {len(self._allowed_tables)} allowed tables from database")
        except Exception as error:
            logging.error(f"Failed to load allowed tables, using safe defaults: {error}")
            # Fallback to minimal safe set
            self._allowed_tables = {
                'MV_CREATOR_PAYMENTS_UNION',
                'V_CREATOR_PAYMENTS_UNION',
                'AI_USER_ACTIVITY_LOG',
                'AI_BUSINESS_CONTEXT',
                'AI_SCHEMA_METADATA',
                'AI_VIEW_CONSTRAINTS',
                'AI_CORTEX_PROMPTS',
                'AI_CORTEX_USAGE_LOG'
            }
    
    def validate_sql_query(self, sql: str) -> SqlValidationResult:
        """Comprehensive SQL query validation with dynamic table checking"""
        sql_upper = sql.upper().strip()
        
        # Check for dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, sql_upper, re.IGNORECASE):
                return SqlValidationResult(
                    is_valid=False,
                    error=f"Dangerous SQL operation detected: {pattern}"
                )
        
        # Verify it's a read-only operation
        if not self.is_read_only_query(sql):
            return SqlValidationResult(
                is_valid=False,
                error="Only read-only operations (SELECT, SHOW, DESCRIBE) are allowed"
            )
        
        # Validate table access with dynamically loaded tables
        table_validation = self.validate_table_access(sql)
        if not table_validation.is_valid:
            return table_validation
        
        return SqlValidationResult(is_valid=True)

    def is_read_only_query(self, sql: str) -> bool:
        """Check if SQL query is read-only"""
        sql_upper = sql.strip().upper()
        return any(sql_upper.startswith(keyword) for keyword in self.READ_ONLY_KEYWORDS)

    def validate_table_access(self, sql: str) -> SqlValidationResult:
        """Validate that query only accesses allowed tables"""
        sql_upper = sql.upper()
        
        # Extract table names from SQL
        table_references = re.findall(r'FROM\s+(\w+)', sql_upper)
        table_references.extend(re.findall(r'JOIN\s+(\w+)', sql_upper))
        
        # Check if any referenced table is not in allowed list
        for table in table_references:
            if table not in self._allowed_tables:
                return SqlValidationResult(
                    is_valid=False,
                    error=f"Access to table '{table}' is not allowed. Allowed tables: {', '.join(sorted(self._allowed_tables))}"
                )
        
        return SqlValidationResult(is_valid=True)
    
    def refresh_allowed_tables(self) -> None:
        """Refresh the allowed tables list from database"""
        self._load_allowed_tables()

    @staticmethod
    def format_database_error(error: Exception) -> str:
        """Format database error for safe client consumption"""
        error_str = str(error).lower()
        
        if "connection" in error_str:
            return "Database connection error"
        elif "permission" in error_str or "access" in error_str:
            return "Database permission error"
        elif "timeout" in error_str:
            return "Database query timeout"
        elif "syntax" in error_str:
            return "SQL syntax error"
        else:
            return "Database operation failed"