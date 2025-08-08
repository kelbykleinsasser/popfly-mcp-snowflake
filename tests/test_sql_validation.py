import pytest

from validators.sql_validator import SqlValidator

class TestSqlValidator:
    
    def test_valid_select_query(self):
        """Test validation of valid SELECT query"""
        sql = "SELECT creator_name, payment_amount FROM V_CREATOR_PAYMENTS_UNION WHERE payment_status = 'PAID'"
        result = SqlValidator.validate_sql_query(sql)
        assert result.is_valid is True
    
    def test_dangerous_drop_query(self):
        """Test validation rejects DROP statements"""
        sql = "DROP TABLE V_CREATOR_PAYMENTS_UNION"
        result = SqlValidator.validate_sql_query(sql)
        assert result.is_valid is False
        assert "DROP" in result.error
    
    def test_dangerous_delete_query(self):
        """Test validation rejects DELETE statements"""
        sql = "DELETE FROM V_CREATOR_PAYMENTS_UNION WHERE payment_id = 1"
        result = SqlValidator.validate_sql_query(sql)
        assert result.is_valid is False
        assert "DELETE" in result.error
    
    def test_sql_injection_attempt(self):
        """Test validation rejects SQL injection patterns"""
        sql = "SELECT * FROM V_CREATOR_PAYMENTS_UNION WHERE creator_name = 'test' OR '1'='1'"
        result = SqlValidator.validate_sql_query(sql)
        assert result.is_valid is False
    
    def test_read_only_validation(self):
        """Test read-only query validation"""
        assert SqlValidator.is_read_only_query("SELECT * FROM table") is True
        assert SqlValidator.is_read_only_query("SHOW TABLES") is True
        assert SqlValidator.is_read_only_query("INSERT INTO table") is False
        assert SqlValidator.is_read_only_query("UPDATE table SET") is False
    
    def test_table_access_validation(self):
        """Test table access validation"""
        # Allowed table
        sql = "SELECT * FROM V_CREATOR_PAYMENTS_UNION"
        result = SqlValidator.validate_table_access(sql)
        assert result.is_valid is True
        
        # Disallowed table
        sql = "SELECT * FROM SENSITIVE_TABLE"
        result = SqlValidator.validate_table_access(sql)
        assert result.is_valid is False