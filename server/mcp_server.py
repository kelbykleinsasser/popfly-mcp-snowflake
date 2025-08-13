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
from tools.dynamic_registry import initialize_registry, get_registry

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
            
            # Initialize dynamic tool registry
            initialize_registry()
            
            self.logger.info("Snowflake MCP Server initialized successfully")
            
        except Exception as error:
            self.logger.error(f"Failed to initialize MCP server: {error}")
            raise
            
    def register_handlers(self):
        """Register MCP request handlers using decorators"""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """Return list of available tools from dynamic registry"""
            from utils.logging import log_activity
            
            registry = get_registry()
            
            # Get tools for default group (stdio doesn't support groups yet)
            tools = []
            if registry and registry.tools:
                tools = registry.get_tools_for_group('default')
            else:
                self.logger.warning("Tool registry not available - returning empty tool list")
            
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
            """Handle tool calls using dynamic registry"""
            
            # Capture raw request as JSON string
            raw_request = json.dumps({
                "method": "call_tool",
                "tool_name": name,
                "arguments": arguments
            })
            
            registry = get_registry()
            if not registry:
                return [TextContent(type="text", text="Tool registry not available")]
            
            # Get handler from registry
            handler = registry.get_handler(name)
            if not handler:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
            
            try:
                # Call the handler with appropriate arguments
                # Handlers expect (arguments, bearer_token, request_id, raw_request)
                result = await handler(
                    arguments, 
                    bearer_token=None,  # No bearer token in stdio mode
                    request_id=None,    # No request ID in stdio mode
                    raw_request=raw_request
                )
                
                # Ensure result is a list of TextContent
                if isinstance(result, list):
                    return result
                else:
                    return [TextContent(type="text", text=str(result))]
                    
            except Exception as error:
                self.logger.error(f"Tool execution failed: {error}")
                return [TextContent(type="text", text=f"Tool execution failed: {str(error)}")]
    
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