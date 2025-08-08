import pytest
import asyncio
from unittest.mock import patch

from server.mcp_server import SnowflakeMCP
from config.settings import settings

class TestMCPServerIntegration:
    
    @pytest.mark.asyncio
    async def test_server_initialization(self):
        """Test MCP server initializes successfully"""
        with patch('utils.config.get_environment_snowflake_connection') as mock_conn:
            # Mock successful connection test
            mock_cursor = mock_conn.return_value.cursor.return_value
            mock_cursor.fetchone.return_value = (1,)
            
            server = SnowflakeMCP()
            
            # Should not raise exception
            await server.init()
            
            # Verify tools are registered
            assert len(server.server.tools) > 0
            
            tool_names = [tool.name for tool in server.server.tools]
            expected_tools = [
                'list_databases', 'list_schemas', 'list_tables', 
                'describe_table', 'read_query', 'append_insight', 
                'query_payments'
            ]
            
            for expected_tool in expected_tools:
                assert expected_tool in tool_names
    
    @pytest.mark.asyncio
    async def test_snowflake_connection_failure(self):
        """Test server handles Snowflake connection failure gracefully"""
        with patch('utils.config.get_environment_snowflake_connection') as mock_conn:
            # Mock connection failure
            mock_conn.side_effect = Exception("Connection failed")
            
            server = SnowflakeMCP()
            
            # Should raise exception during init
            with pytest.raises(Exception):
                await server.init()
    
    @pytest.mark.asyncio
    @patch('tools.snowflake_tools.get_environment_snowflake_connection')
    async def test_end_to_end_query_flow(self, mock_get_conn):
        """Test end-to-end query execution flow"""
        # Mock database responses
        mock_conn = mock_get_conn.return_value
        mock_cursor = mock_conn.cursor.return_value
        
        # Mock successful query execution
        mock_cursor.fetchall.return_value = [
            ('John Doe', 1500.0, 'PAID'),
            ('Jane Smith', 2000.0, 'PENDING')
        ]
        mock_cursor.description = [
            ('CREATOR_NAME',), ('PAYMENT_AMOUNT',), ('PAYMENT_STATUS',)
        ]
        
        # Initialize server
        with patch('server.mcp_server.get_environment_snowflake_connection'):
            server = SnowflakeMCP()
            await server.init()
        
        # Find read_query tool
        read_query_tool = None
        for tool in server.server.tools:
            if tool.name == "read_query":
                read_query_tool = tool
                break
        
        # Execute query (using correct column names)
        result = await read_query_tool.handler({
            "query": "SELECT CREATOR_NAME, PAYMENT_AMOUNT, PAYMENT_STATUS FROM V_CREATOR_PAYMENTS_UNION WHERE PAYMENT_AMOUNT > 1000"
        })
        
        # Verify results
        assert "Success" in result["content"][0]["text"]
        assert "2 rows returned" in result["content"][0]["text"]