import re
from typing import Dict, List, Set
from pydantic import BaseModel

class SqlValidationResult(BaseModel):
    is_valid: bool
    error: str = None
    warnings: List[str] = []

class SqlValidator:
    """SQL validation system for security and compliance"""
    
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
    
    ALLOWED_TABLES = {
        'V_CREATOR_PAYMENTS_UNION',
        'AI_USER_ACTIVITY_LOG',
        'AI_BUSINESS_CONTEXT', 
        'AI_SCHEMA_METADATA',
        'AI_VIEW_CONSTRAINTS',
        'AI_CORTEX_PROMPTS',
        'AI_CORTEX_USAGE_LOG'
    }
    
    ALLOWED_COLUMNS_V_CREATOR_PAYMENTS = {
        'USER_ID', 'CREATOR_NAME', 'COMPANY_NAME', 'CAMPAIGN_NAME',
        'REFERENCE_TYPE', 'REFERENCE_ID', 'PAYMENT_TYPE',
        'PAYMENT_AMOUNT', 'PAYMENT_STATUS', 'PAYMENT_DATE',
        'CREATED_DATE', 'STRIPE_CUSTOMER_ID', 'STRIPE_CUSTOMER_NAME',
        'STRIPE_CONNECTED_ACCOUNT_ID', 'STRIPE_CONNECTED_ACCOUNT_NAME'
    }

    @classmethod
    def validate_sql_query(cls, sql: str) -> SqlValidationResult:
        """Comprehensive SQL query validation"""
        sql_upper = sql.upper().strip()
        
        # Check for dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, sql_upper, re.IGNORECASE):
                return SqlValidationResult(
                    is_valid=False,
                    error=f"Dangerous SQL operation detected: {pattern}"
                )
        
        # Verify it's a read-only operation
        if not cls.is_read_only_query(sql):
            return SqlValidationResult(
                is_valid=False,
                error="Only read-only operations (SELECT, SHOW, DESCRIBE) are allowed"
            )
        
        # Validate table access
        table_validation = cls.validate_table_access(sql)
        if not table_validation.is_valid:
            return table_validation
        
        return SqlValidationResult(is_valid=True)

    @classmethod
    def is_read_only_query(cls, sql: str) -> bool:
        """Check if SQL query is read-only"""
        sql_upper = sql.strip().upper()
        return any(sql_upper.startswith(keyword) for keyword in cls.READ_ONLY_KEYWORDS)

    @classmethod
    def validate_table_access(cls, sql: str) -> SqlValidationResult:
        """Validate that query only accesses allowed tables"""
        # Extract table names from SQL (simplified approach)
        sql_upper = sql.upper()
        
        # Look for FROM and JOIN clauses
        table_references = re.findall(r'FROM\s+(\w+)', sql_upper)
        table_references.extend(re.findall(r'JOIN\s+(\w+)', sql_upper))
        
        # Check if any referenced table is not in allowed list
        for table in table_references:
            if table not in cls.ALLOWED_TABLES:
                return SqlValidationResult(
                    is_valid=False,
                    error=f"Access to table '{table}' is not allowed. Allowed tables: {', '.join(cls.ALLOWED_TABLES)}"
                )
        
        return SqlValidationResult(is_valid=True)

    @classmethod
    def format_database_error(cls, error: Exception) -> str:
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