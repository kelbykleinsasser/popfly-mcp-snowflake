from mcp.server import Server
from mcp.types import Tool, TextContent
import asyncio
import json
from typing import Any, Dict

class SnowflakeMCPServer:
    def __init__(self):
        self.server = Server("snowflake-mcp")
        self.config = Config()  # Handles env switching
        self.connection = self._get_snowflake_connection()
        self.tools = self._initialize_tools()
        self.setup_handlers()
        
    def setup_handlers(self):
        # Add authentication to handlers
        @self.server.list_tools()
        @require_auth
        async def list_tools(request) -> list[Tool]:
            return [
                Tool(
                    name=name,
                    description=tool.description,
                    inputSchema=tool.input_schema
                )
                for name, tool in self.tools.items()
            ]
            
        @self.server.call_tool()
        @require_auth
        async def call_tool(request, name: str, arguments: Dict[str, Any]) -> list[TextContent]:
            if name not in self.tools:
                raise ValueError(f"Unknown tool: {name}")
            
            result = await self.tools[name].execute(arguments)
            return [TextContent(type="text", text=json.dumps(result))]
