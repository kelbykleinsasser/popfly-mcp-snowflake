# Dynamic MCP Tool System - Project Details

## Overview

This document describes the implementation of a fully dynamic, table-driven Model Context Protocol (MCP) tool system for the Popfly Snowflake MCP Server. The system was built to enable adding new tools without modifying Python code, support group-based access control, and maintain complete backward compatibility with existing implementations.

## Why This Was Built

### Problems Solved

1. **Static Tool Registration**: Previously, adding a new tool required modifying Python code, redeploying, and restarting the server
2. **No Access Control**: All tools were available to all users regardless of their role or permissions
3. **Code Maintenance**: Each new tool required changes across multiple files
4. **Scalability**: As tools grew, the codebase became increasingly complex

### Benefits of Dynamic System

1. **Database-Driven**: Add new tools by inserting records into database tables
2. **Group-Based Access**: Different user groups get different sets of tools
3. **Single Handler**: One implementation serves all groups, reducing code duplication
4. **Hot Swappable**: Tools can be enabled/disabled via database without code changes
5. **Audit Trail**: All tool configurations are tracked in database with timestamps

## Architecture

### Database Schema

The system uses three core tables with auto-incrementing IDs:

#### AI_MCP_TOOLS
- Stores tool definitions including name, description, and input schema
- `HANDLER_MODULE` and `HANDLER_FUNCTION` specify the Python implementation
- `IS_SHARED` flag makes a tool available to all groups
- `USES_CORTEX` flag indicates tools that use Snowflake's COMPLETE function for SQL generation
- `IS_ACTIVE` allows enabling/disabling tools without deletion

#### AI_MCP_USER_GROUPS
- Defines user groups with unique URL paths
- `GROUP_PATH` maps to URL segments (e.g., 'admins' → /admins/tools)
- `IS_DEFAULT` identifies the fallback group for unspecified paths

#### AI_MCP_TOOL_GROUP_ACCESS
- Maps non-shared tools to specific groups
- Only needed for tools where `IS_SHARED = FALSE`
- Enables fine-grained access control

### Python Components

#### Dynamic Registry (`tools/dynamic_registry.py`)
- Loads tool definitions from database on startup
- Dynamically imports Python handlers using `importlib`
- Manages group-based access control
- Provides single entry point for all tool calls

#### HTTP Server Updates (`server/mcp_server_http.py`)
- Supports multiple URL paths for different groups
- Routes all requests to dynamic registry
- No fallback to static handlers - fully database-driven
- Returns HTTP 503 if database is unavailable
- Preserves all existing logging and monitoring

#### Handler Organization
- `tools/snowflake_tools.py`: Database query tools
- `tools/payment_tools.py`: Payment-specific tools using Cortex
- `tools/cortex_tools.py`: Natural language query tools

## How the System Works

### Startup Sequence

1. Server starts and validates configuration
2. Dynamic registry connects to Snowflake
3. Registry loads all active tools from `AI_MCP_TOOLS`
4. For each tool, registry:
   - Dynamically imports the Python module
   - Caches the handler function
   - Maps tool to appropriate groups
5. Server is ready to handle requests

### Request Flow

1. **Tool List Request** (`GET /admins/tools`):
   - Extract group from URL path ('admins')
   - Query registry for tools available to that group
   - Return filtered tool list with schemas

2. **Tool Execution** (`POST /admins/tools/call`):
   - Extract group and validate access
   - Load handler from registry cache
   - Execute handler with arguments
   - Log activity with full context
   - Return results

### Group-Based Access

- **Shared Tools**: Available to all groups (e.g., `read_query`)
- **Group-Specific**: Only available to assigned groups (e.g., `query_payments`)
- **Default Group**: Fallback for base URL path (`/tools`)
- **Authorization**: Enforced at registry level before handler execution

## Current Configuration

### Deployed Tools

| Tool Name | Type | Groups | Description |
|-----------|------|--------|-------------|
| query_payments | Restricted | Admins, Account Managers | Natural language payment queries using Cortex AI |

### Internal-Only Tools

| Tool Name | Description | Usage |
|-----------|-------------|-------|
| read_query | Execute SQL SELECT queries directly | Called internally by other tools like query_payments. Not exposed to LLM to prevent arbitrary SQL execution |

### User Groups

| Group Name | URL Path | Description |
|------------|----------|-------------|
| Default | / | Base access for unauthenticated paths |
| Admins | /admins | Full administrative access |
| Account Managers | /accountmanagers | Payment query access |

## How to Use

### Configuring in Open WebUI

When setting up MCP server connections in Open WebUI:

1. **Display Name**: Can be anything descriptive for your users (e.g., "Payment Team", "Data Analysts", "Super Admins")
2. **URL Configuration**: Must use the exact `GROUP_PATH` from your database:
   - `https://mcp.popfly.com/tools` → Default group
   - `https://mcp.popfly.com/admins/tools` → Admins group  
   - `https://mcp.popfly.com/accountmanagers/tools` → Account Managers group
3. **Invalid URLs**: The server now properly validates group paths and returns HTTP 404 for unknown groups, preventing false "Connection Successful" messages

Example Open WebUI Configuration:
```
Name: "Payment Processing Team"  ← Can be anything
URL: https://mcp.popfly.com/accountmanagers/tools  ← Must match GROUP_PATH
```

### Adding a New Tool

1. **Create the Handler** (Python):
```python
# tools/your_module.py
async def your_tool_handler(arguments: Dict[str, Any], 
                            bearer_token: str = None, 
                            request_id: str = None) -> List[TextContent]:
    """Your tool implementation"""
    # Validate inputs with Pydantic
    # Execute business logic
    # Log activity
    # Return results
```

2. **Insert Tool Definition** (SQL):
```sql
INSERT INTO PF.BI.AI_MCP_TOOLS (
    TOOL_NAME,
    TOOL_DESCRIPTION,
    INPUT_SCHEMA,
    HANDLER_MODULE,
    HANDLER_FUNCTION,
    IS_SHARED,
    USES_CORTEX
) VALUES (
    'your_tool_name',
    'Detailed description for the LLM to understand when to use this tool',
    PARSE_JSON('{
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "Parameter description"}
        },
        "required": ["param1"]
    }'),
    'tools.your_module',
    'your_tool_handler',
    FALSE,  -- TRUE if available to all groups
    FALSE   -- TRUE if using Cortex COMPLETE
);
```

3. **Assign to Groups** (if not shared):
```sql
INSERT INTO PF.BI.AI_MCP_TOOL_GROUP_ACCESS (TOOL_ID, GROUP_ID)
SELECT t.TOOL_ID, g.GROUP_ID
FROM PF.BI.AI_MCP_TOOLS t
CROSS JOIN PF.BI.AI_MCP_USER_GROUPS g
WHERE t.TOOL_NAME = 'your_tool_name'
  AND g.GROUP_NAME IN ('Admins', 'Account Managers');
```

4. **Restart Server** to load the new tool

### Creating a New Group

1. **Insert Group Definition**:
```sql
INSERT INTO PF.BI.AI_MCP_USER_GROUPS (
    GROUP_NAME,
    GROUP_PATH,
    DESCRIPTION,
    IS_DEFAULT,
    IS_ACTIVE
) VALUES (
    'Analysts',
    'analysts',
    'Data analyst group with read-only access',
    FALSE,
    TRUE
);
```

2. **Configure in Open WebUI**:
   - Set tool URL to: `https://mcp.popfly.com/analysts/tools`
   - Tools assigned to this group will be available
   - **Note**: The display name in Open WebUI can be anything you want (e.g., "Data Team", "Analysts Group", etc.) - only the URL path matters for group routing

### Disabling a Tool

```sql
-- Temporarily disable a tool
UPDATE PF.BI.AI_MCP_TOOLS 
SET IS_ACTIVE = FALSE 
WHERE TOOL_NAME = 'tool_to_disable';
```

### Testing Tools

Run the comprehensive test suite:
```bash
source venv/bin/activate
python -m tests.test_dynamic_tools
```

The test validates:
- Database connectivity
- Tool loading from database
- Handler imports and validation
- Group-based access control
- Input schema validation
- Actual tool execution
- Authorization enforcement

## Important Design Decisions

### Why No Caching?

For a system with "a handful of users", caching adds unnecessary complexity:
- Real-time data is more important than millisecond response times
- Snowflake queries are already optimized
- Cache invalidation logic would complicate the system
- Payment data should always be fresh

### Why Restart Required?

Tools are loaded at startup for:
- **Performance**: No database queries during request handling
- **Reliability**: Invalid handlers caught at startup, not runtime
- **Security**: Handler validation happens once in controlled environment
- **Simplicity**: No complex hot-reload logic needed

### Why No Fallback to Static Tools?

The system is now 100% database-driven with no hardcoded tool definitions:
- **Single Source of Truth**: All tool configurations come from the database
- **Consistency**: No risk of static and dynamic tools getting out of sync
- **Explicit Failure**: If database is down, the system fails clearly (HTTP 503) rather than running with partial functionality
- **Simplicity**: No need to maintain two parallel tool definition systems

### Why Internal-Only Tools?

Some tools should only be callable by other tools, not directly by the LLM:
- `read_query`: Prevents users from writing arbitrary SQL while still allowing AI-generated queries
- Provides controlled database access through natural language interfaces
- Maintains security while enabling powerful functionality

### Cortex Integration

Tools using Snowflake's COMPLETE function are flagged with `USES_CORTEX`:
- Helps track AI-powered tools
- Useful for cost monitoring
- Enables different handling if needed in future

## Security Considerations

1. **SQL Injection Protection**: All SQL queries validated before execution
2. **Group Isolation**: Tools check group membership before execution
3. **Bearer Token Auth**: All requests require valid Open WebUI tokens
4. **Audit Logging**: Every tool call logged with full context
5. **Role-Based Access**: Snowflake MCP_ROLE has limited permissions

## Monitoring and Debugging

### Check Tool Configuration
```sql
-- View all tools and their handlers
SELECT TOOL_NAME, HANDLER_MODULE, HANDLER_FUNCTION, IS_SHARED, IS_ACTIVE
FROM PF.BI.AI_MCP_TOOLS
ORDER BY TOOL_ID;

-- View group assignments
SELECT t.TOOL_NAME, g.GROUP_NAME
FROM PF.BI.AI_MCP_TOOL_GROUP_ACCESS tga
JOIN PF.BI.AI_MCP_TOOLS t ON tga.TOOL_ID = t.TOOL_ID
JOIN PF.BI.AI_MCP_USER_GROUPS g ON tga.GROUP_ID = g.GROUP_ID
ORDER BY g.GROUP_NAME, t.TOOL_NAME;
```

### View Activity Logs
```sql
-- Recent tool calls
SELECT USER_EMAIL, ACTION_TYPE, ENTITY_TYPE, ACTION_TIMESTAMP, SUCCESS
FROM PF.BI.AI_USER_ACTIVITY_LOG
WHERE ACTION_TYPE LIKE '%tool%'
ORDER BY ACTION_TIMESTAMP DESC
LIMIT 100;
```

### Test Specific Group Access
```bash
# Test what tools are available to admins
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://mcp.popfly.com/admins/tools

# Test default group
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://mcp.popfly.com/tools
```

## Future Enhancements

While the current system meets all requirements, potential future improvements could include:

1. **Tool Versioning**: Track tool definition changes over time
2. **Dynamic Reload**: Refresh tools without restart (if user base grows)
3. **Tool Analytics**: Track usage patterns and performance metrics
4. **Parameter Validation**: Store Pydantic schemas in database
5. **Tool Dependencies**: Define relationships between tools
6. **Rate Limiting**: Per-group or per-tool request limits

## Migration from Static System

The migration preserved all existing functionality:

1. **Deprecated Tools Removed**: 
   - list_databases, list_schemas, list_tables, describe_table, append_insight
   - These were unused in the current Open WebUI integration

2. **Active Tools Migrated**:
   - `query_payments`: Now database-driven with group restrictions
   - `read_query`: Shared tool available to all groups

3. **Logging Preserved**: 
   - All activity logging remains identical
   - Request IDs link pre/post processing stages
   - Cortex usage tracked separately

4. **Full Migration Complete**:
   - All tool definitions now come from database
   - No hardcoded tool definitions remain
   - Static functions (`get_snowflake_tools()`, `get_cortex_tools()`) return empty lists
   - Server returns HTTP 503 if database is unavailable
   - Existing API endpoints continue working
   - No changes required in Open WebUI configuration

5. **Group Validation Enhanced** (Latest Update):
   - Both `/tools` and `/openapi.json` endpoints validate group paths
   - Invalid groups return HTTP 404 with clear error messages
   - Prevents Open WebUI from showing false "Connection Successful" for invalid URLs
   - Example: `/adminssss/tools` returns: "Unknown group: adminssss. Valid groups are: default, admins, accountmanagers"

## Troubleshooting

### Tools Not Loading

1. Check database connectivity:
```sql
SELECT COUNT(*) FROM PF.BI.AI_MCP_TOOLS;
```

2. Verify handler module exists:
```python
import tools.your_module
```

3. Check server logs for import errors

### Access Denied Errors

1. Verify group assignment:
```sql
SELECT * FROM PF.BI.AI_MCP_TOOL_GROUP_ACCESS
WHERE TOOL_ID = (SELECT TOOL_ID FROM PF.BI.AI_MCP_TOOLS WHERE TOOL_NAME = 'your_tool');
```

2. Check group path in URL matches database

3. Ensure tool is active:
```sql
SELECT IS_ACTIVE FROM PF.BI.AI_MCP_TOOLS WHERE TOOL_NAME = 'your_tool';
```

### Handler Not Found

1. Verify module path and function name:
```sql
SELECT HANDLER_MODULE, HANDLER_FUNCTION 
FROM PF.BI.AI_MCP_TOOLS 
WHERE TOOL_NAME = 'your_tool';
```

2. Test import manually:
```python
from tools.your_module import your_handler_function
```

## Conclusion

The dynamic MCP tool system successfully transforms a static, code-based tool registration into a flexible, database-driven system with group-based access control. It maintains simplicity appropriate for a small user base while providing the flexibility to add new tools without code changes. The system is production-ready, fully tested, and preserves all existing functionality while adding powerful new capabilities.