import asyncio
import json
import logging
from typing import Any, Dict, List
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.lowlevel.server import InitializationOptions
from mcp.types import TextContent, Tool

from config.settings import settings
from utils.config import get_environment_snowflake_connection, setup_logging
from tools.snowflake_tools import get_snowflake_tools
from tools.cortex_tools import get_cortex_tools

class SnowflakeMCP:
    def __init__(self):
        self.server = Server("Snowflake MCP Server")
        setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # Register MCP handlers using decorators
        self.register_handlers()
        
    async def init(self):
        """Initialize the MCP server with tools and resources"""
        try:
            # Validate configuration
            settings.validate_required_settings()
            
            # Test Snowflake connection
            await self.test_snowflake_connection()
            
            self.logger.info("Snowflake MCP Server initialized successfully")
            
        except Exception as error:
            self.logger.error(f"Failed to initialize MCP server: {error}")
            raise
            
    def register_handlers(self):
        """Register MCP request handlers using decorators"""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """Return list of available tools"""
            from utils.logging import log_activity
            
            tools = []
            tools.extend(get_snowflake_tools())
            tools.extend(get_cortex_tools())
            
            # Log the list_tools operation for consistency with HTTP server
            await log_activity(
                tool_name="list_tools",
                arguments={},
                row_count=len(tools),
                processing_stage="post",
                execution_success=True
            )
            
            return tools
            
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls with raw request logging"""
            from tools.snowflake_tools import handle_snowflake_tool
            from tools.cortex_tools import handle_cortex_tool
            
            # Capture raw request as JSON string
            raw_request = json.dumps({
                "method": "call_tool",
                "tool_name": name,
                "arguments": arguments
            })
            
            # Route to appropriate tool handler with raw request
            if name in ['list_databases', 'list_schemas', 'list_tables', 'describe_table', 'read_query', 'append_insight']:
                return await handle_snowflake_tool(name, arguments, raw_request=raw_request)
            elif name in ['query_payments']:
                return await handle_cortex_tool(name, arguments, raw_request=raw_request)
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
    
    async def test_snowflake_connection(self):
        """Test Snowflake connectivity during startup"""
        try:
            conn = get_environment_snowflake_connection()
            
            cursor = conn.cursor()
            cursor.execute("SELECT 1 as test")
            result = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            self.logger.info(f"Snowflake connection test passed: {result}")
            
        except Exception as error:
            self.logger.error(f"Snowflake connection test failed: {error}")
            raise
    
    def register_resources(self):
        """Register MCP resources"""
        @self.server.resource("memo://insights")
        async def insights_memo(uri: str) -> Dict[str, Any]:
            """Data insights memo resource"""
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "text/plain",
                        "text": "# Data Insights Memo\n\nInsights discovered during data analysis will be recorded here.\n"
                    }
                ]
            }

async def main():
    """Main entry point for the MCP server"""
    try:
        # Initialize MCP server
        mcp_server = SnowflakeMCP()
        await mcp_server.init()
        
        # Start server
        async with stdio_server() as (read_stream, write_stream):
            await mcp_server.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="Snowflake MCP Server",
                    server_version="1.0.0",
                    capabilities={}
                )
            )
            
    except KeyboardInterrupt:
        logging.info("Server shutdown requested")
    except Exception as error:
        logging.error(f"Server error: {error}")
        raise

if __name__ == "__main__":
    asyncio.run(main())