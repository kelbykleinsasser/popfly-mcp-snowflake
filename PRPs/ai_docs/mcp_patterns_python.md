# MCP Server Development Patterns (Python)

This document contains proven patterns for developing Model Context Protocol (MCP) servers using Python, based on the implementation in this codebase.

## Core MCP Server Architecture

### Base Server Class Pattern

```python
from typing import Dict, Any, Optional
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
import asyncio
import logging

# Authentication props from OAuth flow
class Props:
    def __init__(self, login: str, name: str, email: str, access_token: str):
        self.login = login
        self.name = name
        self.email = email
        self.access_token = access_token

class CustomMCP:
    def __init__(self, props: Props):
        self.props = props
        self.server = Server("Your MCP Server Name")
        
        # CRITICAL: Initialize cleanup handlers
        self._setup_cleanup()
        
    def _setup_cleanup(self):
        """Setup cleanup handlers for graceful shutdown"""
        import atexit
        atexit.register(self.cleanup)
        
    async def cleanup(self):
        """CRITICAL: Implement cleanup for resources"""
        try:
            # Close database connections
            await self._close_db_connections()
            logging.info('Database connections closed successfully')
        except Exception as error:
            logging.error(f'Error during database cleanup: {error}')
    
    async def _close_db_connections(self):
        """Close all database connections"""
        # Implementation depends on your database library
        pass
    
    async def init(self):
        """Initialize all tools and resources"""
        # Register tools here
        self._register_tools()
        
        # Register resources if needed
        self._register_resources()
    
    def _register_tools(self):
        """Tool registration logic"""
        pass
    
    def _register_resources(self):
        """Resource registration logic"""
        pass
```

### Tool Registration Pattern

```python
from mcp.server.models import Tool
from mcp.types import TextContent
import json

# Basic tool registration
async def tool_handler(params: Dict[str, Any]) -> Dict[str, Any]:
    """Tool implementation"""
    try:
        param1 = params.get('param1')
        param2 = params.get('param2')
        
        # Tool implementation
        result = await perform_operation(param1, param2)
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Success: {json.dumps(result, indent=2)}"
                }
            ]
        }
    except Exception as error:
        logging.error(f'Tool error: {error}')
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error: {str(error)}",
                    "isError": True
                }
            ]
        }

# Register the tool
@self.server.tool("toolName")
async def tool_name(params: Dict[str, Any]) -> Dict[str, Any]:
    """Tool description for the LLM"""
    return await tool_handler(params)
```

### Conditional Tool Registration (Based on Permissions)

```python
# Permission-based tool availability
ALLOWED_USERNAMES = {
    'admin1',
    'admin2'
}

# Register privileged tools only for authorized users
if self.props.login in ALLOWED_USERNAMES:
    @self.server.tool("privilegedTool")
    async def privileged_tool(params: Dict[str, Any]) -> Dict[str, Any]:
        """Tool only available to authorized users"""
        # Privileged operation
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Privileged operation executed by: {self.props.login}"
                }
            ]
        }
```

## Database Integration Patterns

### Database Connection Pattern

```python
import asyncpg
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any
import re

class DatabaseManager:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self._pool: Optional[asyncpg.Pool] = None
    
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection with automatic cleanup"""
        if not self._pool:
            self._pool = await asyncpg.create_pool(self.database_url)
        
        async with self._pool.acquire() as conn:
            yield conn
    
    async def close(self):
        """Close database pool"""
        if self._pool:
            await self._pool.close()
            self._pool = None

def validate_sql_query(sql: str) -> Dict[str, Any]:
    """Validate SQL query for security"""
    # Basic SQL injection prevention
    dangerous_patterns = [
        r'DROP\s+TABLE',
        r'DELETE\s+FROM',
        r'TRUNCATE',
        r'ALTER\s+TABLE',
        r'CREATE\s+TABLE',
        r'INSERT\s+INTO',
        r'UPDATE\s+SET'
    ]
    
    sql_upper = sql.upper()
    for pattern in dangerous_patterns:
        if re.search(pattern, sql_upper):
            return {"isValid": False, "error": f"Dangerous SQL operation detected: {pattern}"}
    
    return {"isValid": True}

def is_write_operation(sql: str) -> bool:
    """Check if SQL is a write operation"""
    write_keywords = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'TRUNCATE']
    sql_upper = sql.upper()
    return any(keyword in sql_upper for keyword in write_keywords)

def format_database_error(error: Exception) -> str:
    """Format database error for safe client consumption"""
    # Don't expose internal database details
    if "connection" in str(error).lower():
        return "Database connection error"
    elif "permission" in str(error).lower():
        return "Database permission error"
    else:
        return "Database operation failed"

# Database operation with connection management
async def perform_database_operation(self, sql: str) -> Dict[str, Any]:
    """Execute database operation with proper error handling"""
    try:
        # Validate SQL query
        validation = validate_sql_query(sql)
        if not validation["isValid"]:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Invalid SQL query: {validation['error']}",
                        "isError": True
                    }
                ]
            }
        
        # Execute with automatic connection management
        async with self.db_manager.get_connection() as conn:
            results = await conn.fetch(sql)
            
            # Convert results to JSON-serializable format
            serializable_results = []
            for row in results:
                serializable_results.append(dict(row))
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"**Query Results**\n```sql\n{sql}\n```\n\n**Results:**\n```json\n{json.dumps(serializable_results, indent=2)}\n```\n\n**Rows returned:** {len(serializable_results)}"
                    }
                ]
            }
    except Exception as error:
        logging.error(f'Database operation error: {error}')
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Database error: {format_database_error(error)}",
                    "isError": True
                }
            ]
        }
```

### Read vs Write Operation Handling

```python
# Check if operation is read-only
if is_write_operation(sql):
    return {
        "content": [
            {
                "type": "text",
                "text": "Write operations are not allowed with this tool. Use the privileged tool if you have write permissions.",
                "isError": True
            }
        ]
    }
```

## Authentication & Authorization Patterns

### OAuth Integration Pattern

```python
import aiohttp
from typing import Optional

class OAuthHandler:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
    
    async def get_user_info(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Get user information from OAuth provider"""
        async with aiohttp.ClientSession() as session:
            headers = {'Authorization': f'Bearer {access_token}'}
            async with session.get('https://api.github.com/user', headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                return None

# OAuth configuration
oauth_handler = OAuthHandler(
    client_id=os.getenv('GITHUB_CLIENT_ID'),
    client_secret=os.getenv('GITHUB_CLIENT_SECRET')
)
```

### User Permission Checking

```python
# Permission validation pattern
def has_permission(username: str, operation: str) -> bool:
    """Check if user has permission for operation"""
    WRITE_PERMISSIONS = {'admin1', 'admin2'}
    READ_PERMISSIONS = {'user1', 'user2'}.union(WRITE_PERMISSIONS)
    
    if operation == 'read':
        return username in READ_PERMISSIONS
    elif operation == 'write':
        return username in WRITE_PERMISSIONS
    else:
        return False
```

## Error Handling Patterns

### Standardized Error Response

```python
def create_error_response(error: Exception, operation: str) -> Dict[str, Any]:
    """Create standardized error response"""
    logging.error(f'{operation} error: {error}')
    
    return {
        "content": [
            {
                "type": "text",
                "text": f"{operation} failed: {str(error)}",
                "isError": True
            }
        ]
    }
```

### Database Error Formatting

```python
# Use the built-in database error formatter
try:
    # Database operation
    pass
except Exception as error:
    return {
        "content": [
            {
                "type": "text",
                "text": f"Database error: {format_database_error(error)}",
                "isError": True
            }
        ]
    }
```

## Resource Registration Patterns

### Basic Resource Pattern

```python
# Resource registration
@self.server.resource("resource://example/{id}")
async def example_resource(uri: str) -> Dict[str, Any]:
    """Resource description"""
    try:
        # Extract ID from URI
        id = uri.split('/')[-1]
        
        data = await fetch_resource_data(id)
        
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(data, indent=2)
                }
            ]
        }
    except Exception as error:
        raise Exception(f"Failed to fetch resource: {str(error)}")
```

## Testing Patterns

### Tool Testing Pattern

```python
# Test tool functionality
async def test_tool(tool_name: str, params: Dict[str, Any]) -> bool:
    """Test tool functionality"""
    try:
        result = await server.call_tool(tool_name, params)
        logging.info(f'{tool_name} test passed: {result}')
        return True
    except Exception as error:
        logging.error(f'{tool_name} test failed: {error}')
        return False
```

### Database Connection Testing

```python
# Test database connectivity
async def test_database_connection(database_url: str) -> bool:
    """Test database connectivity"""
    try:
        async with DatabaseManager(database_url) as db_manager:
            async with db_manager.get_connection() as conn:
                result = await conn.fetchval("SELECT 1 as test")
                logging.info(f'Database connection test passed: {result}')
        return True
    except Exception as error:
        logging.error(f'Database connection test failed: {error}')
        return False
```

## Security Best Practices

### Input Validation

```python
from pydantic import BaseModel, validator
from typing import Optional, List

# Always validate inputs with Pydantic
class InputSchema(BaseModel):
    query: str
    parameters: Optional[List[str]] = None
    
    @validator('query')
    def validate_query(cls, v):
        if not v or len(v) > 1000:
            raise ValueError('Query must be between 1 and 1000 characters')
        return v

# In tool handler
try:
    validated = InputSchema(**params)
    # Use validated data
except Exception as error:
    return create_error_response(error, "Input validation")
```

### SQL Injection Prevention

```python
# Use the built-in SQL validation
validation = validate_sql_query(sql)
if not validation["isValid"]:
    return create_error_response(Exception(validation["error"]), "SQL validation")
```

### Access Control

```python
# Always check permissions before executing sensitive operations
if not has_permission(self.props.login, 'write'):
    return {
        "content": [
            {
                "type": "text",
                "text": "Access denied: insufficient permissions",
                "isError": True
            }
        ]
    }
```

## Performance Patterns

### Connection Pooling

```python
# Use the built-in connection pooling
async with self.db_manager.get_connection() as conn:
    # Database operations
    pass
```

### Resource Cleanup

```python
# Implement proper cleanup
async def cleanup(self):
    """Implement proper cleanup"""
    try:
        # Close database connections
        await self.db_manager.close()
        
        # Clean up other resources
        await self._cleanup_resources()
        
        logging.info('Cleanup completed successfully')
    except Exception as error:
        logging.error(f'Cleanup error: {error}')
```

## Common Gotchas

### 1. Missing Cleanup Implementation
- Always implement cleanup methods
- Handle database connection cleanup properly
- Use context managers for resource management

### 2. SQL Injection Vulnerabilities
- Always use `validate_sql_query()` before executing SQL
- Never concatenate user input directly into SQL strings
- Use parameterized queries when possible

### 3. Permission Bypasses
- Check permissions for every sensitive operation
- Don't rely on tool registration alone for security
- Always validate user identity from props

### 4. Error Information Leakage
- Use `format_database_error()` to sanitize error messages
- Don't expose internal system details in error responses
- Log detailed errors server-side, return generic messages to client

### 5. Resource Leaks
- Always use context managers for database operations
- Implement proper error handling in async operations
- Clean up resources in finally blocks

### 6. Async/Await Patterns
- Always use `async`/`await` for database operations
- Don't block the event loop with synchronous operations
- Use `asyncio.gather()` for concurrent operations

## Environment Configuration

### Required Environment Variables

```python
import os
from typing import Optional

class Environment:
    """Environment configuration"""
    DATABASE_URL: str = os.getenv('DATABASE_URL', '')
    GITHUB_CLIENT_ID: str = os.getenv('GITHUB_CLIENT_ID', '')
    GITHUB_CLIENT_SECRET: str = os.getenv('GITHUB_CLIENT_SECRET', '')
    
    @classmethod
    def validate(cls) -> bool:
        """Validate required environment variables"""
        required_vars = ['DATABASE_URL', 'GITHUB_CLIENT_ID', 'GITHUB_CLIENT_SECRET']
        missing = [var for var in required_vars if not getattr(cls, var)]
        
        if missing:
            logging.error(f"Missing required environment variables: {missing}")
            return False
        return True
```

### Requirements.txt Pattern

```txt
# requirements.txt
mcp>=1.0.0
asyncpg>=0.28.0
aiohttp>=3.8.0
pydantic>=2.0.0
python-dotenv>=1.0.0
```

### Main Application Pattern

```python
import asyncio
import logging
from mcp.server.stdio import stdio_server

async def main():
    """Main application entry point"""
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Validate environment
    if not Environment.validate():
        raise ValueError("Invalid environment configuration")
    
    # Initialize MCP server
    props = Props(
        login="user",
        name="User Name",
        email="user@example.com",
        access_token="token"
    )
    
    mcp_server = CustomMCP(props)
    await mcp_server.init()
    
    # Start server
    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.server.run(
            read_stream,
            write_stream,
            InitializationOptions()
        )

if __name__ == "__main__":
    asyncio.run(main())
```

## Testing Configuration

### Pytest Configuration Pattern

```python
# conftest.py
import pytest
import asyncio
from typing import AsyncGenerator

@pytest.fixture
async def database_manager() -> AsyncGenerator[DatabaseManager, None]:
    """Database manager fixture for testing"""
    manager = DatabaseManager("postgresql://test:test@localhost/test")
    yield manager
    await manager.close()

@pytest.fixture
async def mcp_server() -> AsyncGenerator[CustomMCP, None]:
    """MCP server fixture for testing"""
    props = Props("testuser", "Test User", "test@example.com", "test_token")
    server = CustomMCP(props)
    await server.init()
    yield server
    await server.cleanup()
```

This document provides the core patterns for building secure, scalable MCP servers using Python, adapting the proven architecture from the TypeScript implementation.
