#!/usr/bin/env python3
"""
CLI tool for testing the Snowflake MCP server manually
"""

import asyncio
import json
import sys
from typing import Dict, Any

from server.mcp_server import SnowflakeMCP

class MCPServerCLI:
    """Command-line interface for testing MCP server"""
    
    def __init__(self):
        self.server = None
    
    async def initialize(self):
        """Initialize the MCP server"""
        try:
            self.server = SnowflakeMCP()
            await self.server.init()
            print("✅ MCP Server initialized successfully")
            return True
        except Exception as error:
            print(f"❌ Failed to initialize MCP server: {error}")
            return False
    
    async def list_tools(self):
        """List all available tools"""
        if not self.server:
            print("❌ Server not initialized")
            return
        
        print("\n📋 Available Tools:")
        print("-" * 50)
        
        # Get tools from the tool modules directly
        from tools.snowflake_tools import get_snowflake_tools
        from tools.cortex_tools import get_cortex_tools
        from utils.logging import log_activity
        
        tools = []
        tools.extend(get_snowflake_tools())
        tools.extend(get_cortex_tools())
        
        # Log the list_tools operation
        await log_activity(
            tool_name="list_tools",
            arguments={},
            row_count=len(tools),
            processing_stage="post",
            execution_success=True
        )
        
        for tool in tools:
            print(f"🔧 {tool.name}")
            print(f"   Description: {tool.description}")
            if hasattr(tool, 'inputSchema'):
                required_params = tool.inputSchema.get('required', [])
                if required_params:
                    print(f"   Required parameters: {', '.join(required_params)}")
            print()
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]):
        """Call a specific tool with arguments"""
        if not self.server:
            print("❌ Server not initialized")
            return
        
        # Get available tools
        from tools.snowflake_tools import get_snowflake_tools
        from tools.cortex_tools import get_cortex_tools
        
        tools = []
        tools.extend(get_snowflake_tools())
        tools.extend(get_cortex_tools())
        
        # Find the tool
        target_tool = None
        for tool in tools:
            if tool.name == tool_name:
                target_tool = tool
                break
        
        if not target_tool:
            print(f"❌ Tool '{tool_name}' not found")
            return
        
        try:
            print(f"🚀 Calling tool: {tool_name}")
            print(f"📝 Arguments: {json.dumps(arguments, indent=2)}")
            print("-" * 50)
            
            # Call the tool handlers directly with raw request
            from tools.snowflake_tools import handle_snowflake_tool
            from tools.cortex_tools import handle_cortex_tool
            
            # Capture raw request for logging
            raw_request = json.dumps({
                "method": "cli_call",
                "tool_name": tool_name,
                "arguments": arguments
            })
            
            if tool_name in ['list_databases', 'list_schemas', 'list_tables', 'describe_table', 'read_query', 'append_insight']:
                result = await handle_snowflake_tool(tool_name, arguments, raw_request=raw_request)
            elif tool_name in ['query_payments']:
                result = await handle_cortex_tool(tool_name, arguments, raw_request=raw_request)
            else:
                print(f"❌ Unknown tool: {tool_name}")
                return
            
            print("📊 Result:")
            if isinstance(result, list):
                for content in result:
                    if hasattr(content, 'text'):
                        print(content.text)
                    elif isinstance(content, dict) and content.get("type") == "text":
                        print(content["text"])
            else:
                print(json.dumps(result, indent=2))
                
        except Exception as error:
            print(f"❌ Tool execution failed: {error}")
    
    def print_usage(self):
        """Print CLI usage instructions"""
        print("""
🔧 Snowflake MCP Server CLI

Usage:
python -m cli.mcp_cli <command> [arguments]

Commands:

init                          - Initialize the MCP server
list                         - List all available tools  
call <tool_name> <json_args> - Call a tool with JSON arguments

Examples:

# Initialize server
python -m cli.mcp_cli init

# List available tools
python -m cli.mcp_cli list

# Call list_databases tool
python -m cli.mcp_cli call list_databases '{}'

# Call read_query tool
python -m cli.mcp_cli call read_query '{"query": "SELECT * FROM V_CREATOR_PAYMENTS_UNION LIMIT 5"}'

# Call query_payments tool with natural language
python -m cli.mcp_cli call query_payments '{"query": "Show me payments over $1000 from last month"}'
""")

async def main():
    """Main CLI function"""
    cli = MCPServerCLI()
    
    if len(sys.argv) < 2:
        cli.print_usage()
        return
    
    command = sys.argv[1].lower()
    
    if command == "init":
        success = await cli.initialize()
        if success:
            print("\n✅ Server ready for testing")
        else:
            sys.exit(1)
    
    elif command == "list":
        await cli.initialize()
        await cli.list_tools()
    
    elif command == "call":
        if len(sys.argv) < 4:
            print("❌ Usage: call <tool_name> <json_arguments>")
            return
        
        tool_name = sys.argv[2]
        try:
            arguments = json.loads(sys.argv[3])
        except json.JSONDecodeError as error:
            print(f"❌ Invalid JSON arguments: {error}")
            return
        
        await cli.initialize()
        await cli.call_tool(tool_name, arguments)
    
    else:
        print(f"❌ Unknown command: {command}")
        cli.print_usage()

if __name__ == "__main__":
    asyncio.run(main())