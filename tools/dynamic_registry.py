"""
Dynamic Tool Registry for MCP Server
Loads tool definitions from database and manages handler routing
"""
import importlib
import json
import logging
from typing import Dict, Any, List, Optional, Callable
from mcp.types import Tool, TextContent
from utils.config import get_environment_snowflake_connection
from utils.connection_pool import get_pooled_connection
from pydantic import BaseModel


class DynamicTool(BaseModel):
    """Represents a dynamically loaded tool from database"""
    tool_id: int
    tool_name: str
    tool_description: str
    input_schema: Dict[str, Any]
    handler_module: str
    handler_function: str
    is_shared: bool
    is_active: bool
    uses_cortex: bool


class DynamicToolRegistry:
    """Registry for dynamically loaded MCP tools"""
    
    def __init__(self):
        self.handlers: Dict[str, Callable] = {}
        self.tools: Dict[str, DynamicTool] = {}
        self.tools_by_group: Dict[str, List[str]] = {}
        self.groups: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger(__name__)
        
    def load_from_database(self) -> None:
        """Load all tools and groups from database on startup"""
        self.logger.info("Loading dynamic tools from database...")
        
        try:
            with get_pooled_connection() as conn:
                cursor = conn.cursor()
                
                # Load user groups
                cursor.execute("""
                    SELECT GROUP_ID, GROUP_NAME, GROUP_PATH, DESCRIPTION, IS_DEFAULT
                    FROM PF.BI.AI_MCP_USER_GROUPS
                    WHERE IS_ACTIVE = TRUE
                """)
                
                for row in cursor.fetchall():
                    group_id, group_name, group_path, description, is_default = row
                    self.groups[group_path or 'default'] = {
                        'id': group_id,
                        'name': group_name,
                        'description': description,
                        'is_default': is_default
                    }
                    self.tools_by_group[group_path or 'default'] = []
                
                # Load active tools
                cursor.execute("""
                    SELECT TOOL_ID, TOOL_NAME, TOOL_DESCRIPTION, INPUT_SCHEMA,
                           HANDLER_MODULE, HANDLER_FUNCTION, IS_SHARED, USES_CORTEX
                    FROM PF.BI.AI_MCP_TOOLS
                    WHERE IS_ACTIVE = TRUE
                """)
                
                for row in cursor.fetchall():
                    tool_id, tool_name, tool_description, input_schema, handler_module, handler_function, is_shared, uses_cortex = row
                    
                    # Create tool object
                    tool = DynamicTool(
                        tool_id=tool_id,
                        tool_name=tool_name,
                        tool_description=tool_description,
                        input_schema=input_schema if isinstance(input_schema, dict) else json.loads(input_schema),
                        handler_module=handler_module,
                        handler_function=handler_function,
                        is_shared=is_shared,
                        is_active=True,
                        uses_cortex=uses_cortex
                    )
                    
                    self.tools[tool_name] = tool
                    
                    # Load handler
                    try:
                        self._load_handler(tool)
                        self.logger.info(f"Loaded tool: {tool_name} from {handler_module}.{handler_function}")
                    except Exception as e:
                        self.logger.error(f"Failed to load handler for {tool_name}: {e}")
                        continue
                    
                    # Map tools to groups
                    if is_shared:
                        # Add to all groups
                        self.logger.info(f"Tool {tool_name} is shared, adding to all groups: {list(self.tools_by_group.keys())}")
                        for group_path in self.tools_by_group:
                            self.tools_by_group[group_path].append(tool_name)
                            self.logger.info(f"Added {tool_name} to group {group_path}")
                    else:
                        # Load specific group mappings
                        cursor.execute("""
                            SELECT g.GROUP_PATH
                            FROM PF.BI.AI_MCP_TOOL_GROUP_ACCESS tga
                            JOIN PF.BI.AI_MCP_USER_GROUPS g ON tga.GROUP_ID = g.GROUP_ID
                            WHERE tga.TOOL_ID = %s AND g.IS_ACTIVE = TRUE
                        """, (tool_id,))
                        
                        for (group_path,) in cursor.fetchall():
                            path = group_path or 'default'
                            if path in self.tools_by_group:
                                self.tools_by_group[path].append(tool_name)
                
                cursor.close()
            
            self.logger.info(f"Loaded {len(self.tools)} tools and {len(self.groups)} groups")
            
        except Exception as e:
            self.logger.error(f"Failed to load tools from database: {e}")
            raise
    
    def _load_handler(self, tool: DynamicTool) -> None:
        """Dynamically import and cache a tool handler"""
        try:
            # Import the module
            module = importlib.import_module(tool.handler_module)
            
            # Get the handler function
            handler = getattr(module, tool.handler_function)
            
            if not callable(handler):
                raise ValueError(f"Handler {tool.handler_function} is not callable")
            
            # Cache the handler
            self.handlers[tool.tool_name] = handler
            
        except ImportError as e:
            raise ImportError(f"Failed to import module {tool.handler_module}: {e}")
        except AttributeError as e:
            raise AttributeError(f"Handler function {tool.handler_function} not found in {tool.handler_module}: {e}")
    
    def get_handler(self, tool_name: str) -> Optional[Callable]:
        """Get handler for a specific tool"""
        return self.handlers.get(tool_name)
    
    def get_tool_definition(self, tool_name: str) -> Optional[DynamicTool]:
        """Get tool definition"""
        return self.tools.get(tool_name)
    
    def get_tools_for_group(self, group_path: Optional[str] = None) -> List[Tool]:
        """Get MCP Tool objects available for a specific group"""
        path = group_path or 'default'
        
        if path not in self.tools_by_group:
            # Unknown group - return empty list or raise error
            # We'll return empty list to indicate invalid group
            self.logger.warning(f"Unknown group path requested: {path}")
            return []
        
        tools = []
        for tool_name in self.tools_by_group.get(path, []):
            if tool_name in self.tools:
                tool_def = self.tools[tool_name]
                tools.append(Tool(
                    name=tool_def.tool_name,
                    description=tool_def.tool_description,
                    inputSchema=tool_def.input_schema
                ))
        
        return tools
    
    def is_valid_group(self, group_path: str) -> bool:
        """Check if a group path is valid"""
        path = group_path or 'default'
        return path in self.tools_by_group
    
    def get_group_from_path(self, request_path: str) -> str:
        """Extract group from request path"""
        # Example paths:
        # /tools -> default
        # /admins/tools -> admins
        # /accountmanagers/tools -> accountmanagers
        
        parts = request_path.strip('/').split('/')
        
        # Check if first part is a known group path
        if len(parts) > 1 and parts[0] in self.groups:
            return parts[0]
        
        return 'default'
    
    async def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any], 
                               bearer_token: str = None, raw_request: str = None,
                               group_path: str = 'default') -> List[TextContent]:
        """Route tool call to appropriate handler"""
        
        # Check if tool exists
        if tool_name not in self.tools:
            return [TextContent(type="text", text=f"Unknown tool: {tool_name}")]
        
        # Check if tool is available for group
        if tool_name not in self.tools_by_group.get(group_path, []):
            return [TextContent(type="text", text=f"Tool {tool_name} not available for this group")]
        
        # Get handler
        handler = self.handlers.get(tool_name)
        if not handler:
            return [TextContent(type="text", text=f"Handler not found for tool: {tool_name}")]
        
        # Call handler
        try:
            # Check if it's an async handler
            import asyncio
            if asyncio.iscoroutinefunction(handler):
                result = await handler(arguments, bearer_token, None)  # request_id will be generated in handler
            else:
                result = handler(arguments, bearer_token, None)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing tool {tool_name}: {e}")
            return [TextContent(type="text", text=f"Error executing tool: {str(e)}")]


# Global registry instance
registry = DynamicToolRegistry()


def initialize_registry():
    """Initialize the global registry - call on server startup"""
    registry.load_from_database()
    return registry


def get_registry() -> DynamicToolRegistry:
    """Get the global registry instance"""
    return registry