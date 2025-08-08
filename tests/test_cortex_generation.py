import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from cortex.cortex_generator import CortexGenerator, CortexRequest

class TestCortexGenerator:
    
    @pytest.mark.asyncio
    @patch('cortex.cortex_generator.get_environment_snowflake_connection')
    async def test_successful_sql_generation(self, mock_get_conn):
        """Test successful SQL generation via Cortex"""
        # Mock database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("SELECT * FROM V_CREATOR_PAYMENTS_UNION LIMIT 10",)
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        
        # Create request
        request = CortexRequest(
            natural_language_query="Show me recent payments",
            view_name="V_CREATOR_PAYMENTS_UNION"
        )
        
        # Generate SQL
        response = await CortexGenerator.generate_sql(request)
        
        # Assertions
        assert response.success is True
        assert response.generated_sql is not None
        assert "SELECT" in response.generated_sql.upper()
    
    def test_cortex_prompt_building(self):
        """Test Cortex prompt construction"""
        request = CortexRequest(
            natural_language_query="Show payments over $1000",
            view_name="V_CREATOR_PAYMENTS_UNION"
        )
        
        constraints = CortexGenerator.VIEW_CONSTRAINTS["V_CREATOR_PAYMENTS_UNION"]
        prompt = CortexGenerator.build_cortex_prompt(request, constraints)
        
        assert "SELECT" in prompt
        assert "V_CREATOR_PAYMENTS_UNION" in prompt
        assert "payments over $1000" in prompt
        assert "PAYMENT_AMOUNT" in prompt
    
    @pytest.mark.asyncio
    async def test_invalid_view_name(self):
        """Test error handling for invalid view name"""
        request = CortexRequest(
            natural_language_query="Show me data",
            view_name="NONEXISTENT_VIEW"
        )
        
        response = await CortexGenerator.generate_sql(request)
        
        assert response.success is False
        assert "not configured" in response.error