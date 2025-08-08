# Snowflake MCP Server - Python Implementation Guide

This guide provides implementation patterns and standards for building a Python-based MCP (Model Context Protocol) server with Snowflake integration and Open WebUI authentication.

## Core Principles

**IMPORTANT: You MUST follow these principles in all code changes and PRP generations:**

### KISS (Keep It Simple, Stupid)

- Simplicity should be a key goal in design
- Choose straightforward solutions over complex ones whenever possible
- Simple solutions are easier to understand, maintain, and debug

### YAGNI (You Aren't Gonna Need It)

- Avoid building functionality on speculation
- Implement features only when they are needed, not when you anticipate they might be useful in the future

### Open/Closed Principle

- Software entities should be open for extension but closed for modification
- Design systems so that new functionality can be added with minimal changes to existing code

## Project Architecture

**IMPORTANT: This is a Python-based MCP server with Snowflake integration and Open WebUI authentication.**

### Current Project Structure

```
/
├── auth/                         # Snowflake authentication modules
│   ├── __init__.py
│   ├── snowflake_auth.py         # Basic RSA key authentication
│   ├── snowflake_auth_secure.py  # Production with Secret Manager
│   ├── snowflake_auth_mcp.py     # MCP-specific auth implementation
│   └── secret_manager.py         # GCP Secret Manager integration
├── server/                       # MCP server implementation
│   ├── __init__.py
│   ├── mcp_server.py            # Main MCP server
│   └── handlers.py              # Request handlers
├── cortex/                      # Snowflake Cortex integration
│   ├── __init__.py
│   ├── sql_generator.py         # Basic Cortex SQL generation
│   └── cortex_generator.py      # Complete Cortex implementation
├── tools/                       # MCP tools
│   ├── __init__.py
│   ├── base_tool.py            # Base class for tools
│   └── natural_language_tool.py # Primary NL tool using Cortex
├── validators/                  # Security validation
│   ├── __init__.py
│   └── sql_validator.py        # SQL validation for security
├── auth_middleware/             # Open WebUI authentication
│   ├── __init__.py
│   └── bearer_auth.py          # Bearer token validation
├── utils/                       # Utilities
│   ├── __init__.py
│   ├── logging.py              # Activity logging
│   ├── cache.py                # Cortex SQL caching
│   └── config.py               # Environment configuration
├── config/                      # Configuration
│   ├── __init__.py
│   └── settings.py             # Environment settings
├── initialsetup/                # Database setup
│   └── sql/
│       ├── 01_create_ai_tables.sql
│       ├── 02_insert_view_constraints.sql
│       └── 03_setup_logging_tables.sql
├── tests/                       # Test suite
│   ├── __init__.py
│   ├── test_auth.py
│   ├── test_cortex_generation.py
│   ├── test_sql_validation.py
│   └── test_integration.py
├── examples/                    # Reference implementations
├── PRPs/                        # Product Requirement Prompts
├── .env.example                 # Environment template
├── requirements.txt             # Python dependencies
├── README.md                    # Project documentation
└── CLAUDE.md                    # This implementation guide
```

## Development Commands

### Core Workflow Commands

```bash
# Setup & Dependencies
pip install -r requirements.txt  # Install Python dependencies
python -m venv venv              # Create virtual environment
source venv/bin/activate         # Activate virtual environment (Linux/Mac)

# Development
python -m server.mcp_server      # Start MCP server
python -m pytest tests/         # Run tests

# Code Quality
black .                          # Format code
ruff check .                     # Lint code
mypy .                          # Type checking
```

### Environment Configuration

**Environment Variables Setup:**

```bash
# Create .env file for local development
cp .env.example .env

# Production secrets (via GCP Secret Manager)
# - SNOWFLAKE_ACCOUNT
# - SNOWFLAKE_USER
# - SNOWFLAKE_PRIVATE_KEY
# - SNOWFLAKE_PRIVATE_KEY_PASSPHRASE
# - OPEN_WEBUI_API_KEY
```

## MCP Development Context

**IMPORTANT: This project builds a Python-based MCP server for Snowflake integration with Open WebUI authentication.**

### MCP Technology Stack

**Core Technologies:**

- **mcp** - Official MCP Python SDK
- **snowflake-connector-python** - Snowflake database connectivity
- **fastapi** - Web framework for MCP server endpoints
- **pydantic** - Data validation and settings
- **asyncio** - Async/await patterns

**Google Cloud Platform:**

- **Secret Manager** - Production secret management
- **Cloud Run** - Serverless deployment
- **Container Registry** - Docker image storage

### MCP Server Architecture

This project implements an MCP server as a Python application with authentication:

**Authenticated Snowflake MCP Server (`server/mcp_server.py`):**

```python
from mcp.server import Server
from mcp.server.models import InitializationOptions

class SnowflakeMCP:
    def __init__(self):
        self.server = Server("Snowflake MCP Server")
        
    # MCP Tools available based on user permissions
    # - list_databases (all users)
    # - list_schemas (all users)  
    # - list_tables (all users)
    # - describe_table (all users)
    # - read_query (all users, read-only)
    # - append_insight (all users)
```

### MCP Development Commands

**Local Development & Testing:**

```bash
# Start MCP server
python -m server.mcp_server     # Available via stdio

# Test with MCP Inspector
npx @modelcontextprotocol/inspector@latest python -m server.mcp_server
```

### Claude Desktop Integration

**For Local Development:**

```json
{
  "mcpServers": {
    "snowflake-mcp": {
      "command": "python",
      "args": ["-m", "server.mcp_server"],
      "cwd": "/path/to/snowflake-mcp",
      "env": {
        "PYTHONPATH": "/path/to/snowflake-mcp"
      }
    }
  }
}
```

## Database Integration & Security

**CRITICAL: This project provides secure Snowflake database access through MCP tools with role-based permissions.**

### Database Architecture

**Connection Management (`auth/snowflake_auth.py`):**

```python
import snowflake.connector
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key

def get_snowflake_connection(
    account: str,
    user: str, 
    private_key_path: str,
    private_key_passphrase: str = None,
    database: str = None,
    schema: str = None,
    warehouse: str = None
) -> snowflake.connector.SnowflakeConnection:
    """Get authenticated Snowflake connection using RSA private key"""
    
    with open(private_key_path, 'rb') as key_file:
        private_key = load_pem_private_key(
            key_file.read(),
            password=private_key_passphrase.encode() if private_key_passphrase else None
        )
    
    pkb = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    return snowflake.connector.connect(
        account=account,
        user=user,
        private_key=pkb,
        database=database,
        schema=schema,
        warehouse=warehouse
    )
```

### Security Implementation

**SQL Injection Protection:**

```python
def validate_sql_query(sql: str) -> dict:
    """Validate SQL query for security"""
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
            return {"isValid": False, "error": f"Dangerous SQL operation: {pattern}"}
    
    return {"isValid": True}

def is_read_only_query(sql: str) -> bool:
    """Check if SQL is read-only"""
    read_keywords = ['SELECT', 'SHOW', 'DESCRIBE', 'EXPLAIN']
    sql_upper = sql.strip().upper()
    return any(sql_upper.startswith(keyword) for keyword in read_keywords)
```

### MCP Tools Implementation

**Available Snowflake Tools:**

1. **`list_databases`** - Database discovery (all authenticated users)
2. **`list_schemas`** - Schema discovery (all authenticated users) 
3. **`list_tables`** - Table discovery (all authenticated users)
4. **`describe_table`** - Table schema information (all authenticated users)
5. **`read_query`** - Execute SELECT queries (all authenticated users)
6. **`append_insight`** - Add insights to memo (all authenticated users)

## Open WebUI Authentication

**CRITICAL: This project implements bearer token authentication for Open WebUI integration.**

### Authentication Flow

**Bearer Token Validation (`auth_middleware/bearer_auth.py`):**

```python
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os

security = HTTPBearer()

def validate_bearer_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Validate bearer token from Open WebUI"""
    expected_token = os.getenv('OPEN_WEBUI_API_KEY')
    
    if not expected_token:
        raise HTTPException(status_code=500, detail="Server configuration error")
    
    if credentials.credentials != expected_token:
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    
    return credentials.credentials
```

## Environment Configuration

**CRITICAL: This project supports local development and GCP production deployment.**

### Required Environment Variables

**Local Development (`.env`):**
```bash
ENVIRONMENT=local
SNOWFLAKE_ACCOUNT=your-account
SNOWFLAKE_USER=your-user
SNOWFLAKE_PRIVATE_KEY_PATH=auth/snowflake_key.pem
SNOWFLAKE_PRIVATE_KEY_PASSPHRASE=your-passphrase
SNOWFLAKE_DATABASE=PF
SNOWFLAKE_SCHEMA=BI
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
OPEN_WEBUI_API_KEY=your-api-key
```

**Production (GCP Secret Manager):**
```bash
ENVIRONMENT=production
GCP_PROJECT_ID=your-project-id
# All other secrets stored in GCP Secret Manager
```

## Python Development Standards

**CRITICAL: All MCP tools MUST follow Python best practices with Pydantic validation and proper error handling.**

### Standard Response Format

**ALL tools MUST return MCP-compatible response objects:**

```python
from pydantic import BaseModel
from typing import Any, Dict, List

class McpResponse(BaseModel):
    content: List[Dict[str, Any]]

def create_success_response(message: str, data: Any = None) -> Dict[str, Any]:
    """Create standardized success response"""
    text = f"**Success**\n\n{message}"
    if data is not None:
        text += f"\n\n**Result:**\n```json\n{json.dumps(data, indent=2, default=str)}\n```"
    
    return {
        "content": [
            {
                "type": "text",
                "text": text
            }
        ]
    }

def create_error_response(message: str, details: Any = None) -> Dict[str, Any]:
    """Create standardized error response"""
    text = f"**Error**\n\n{message}"
    if details is not None:
        text += f"\n\n**Details:**\n```json\n{json.dumps(details, indent=2, default=str)}\n```"
    
    return {
        "content": [
            {
                "type": "text", 
                "text": text,
                "isError": True
            }
        ]
    }
```

### Input Validation with Pydantic

**ALL tool inputs MUST be validated using Pydantic schemas:**

```python
from pydantic import BaseModel, validator

class ReadQuerySchema(BaseModel):
    query: str
    max_rows: int = 1000
    
    @validator('query')
    def validate_query(cls, v):
        if not v.strip():
            raise ValueError("Query cannot be empty")
        if not is_read_only_query(v):
            raise ValueError("Only SELECT queries are allowed")
        return v
    
    @validator('max_rows')
    def validate_max_rows(cls, v):
        if v <= 0 or v > 10000:
            raise ValueError("max_rows must be between 1 and 10000")
        return v
```

## Code Style Preferences

### Python Style

- Use **Black** for code formatting
- Use **Ruff** for linting
- Use **mypy** for type checking
- Use **Pydantic** for all data validation
- Use **async/await** for all I/O operations
- Keep functions focused (single responsibility principle)

### File Organization

- Each MCP server should be organized into logical modules
- Import statements organized: standard library, third-party, local imports
- Use absolute imports from project root
- **Import Pydantic for validation and proper types for all modules**

### Testing Conventions

- Use **pytest** for all testing
- Test with MCP Inspector for integration testing
- Use descriptive test names and docstrings
- **Test both success and failure scenarios**
- **Test input validation with invalid data**

## Important Notes

### What NOT to do

- **NEVER** commit secrets or private keys to the repository
- **NEVER** skip input validation with Pydantic schemas
- **NEVER** expose internal Snowflake errors to clients

### What TO do

- **ALWAYS** use Pydantic for input validation
- **ALWAYS** use proper async/await patterns
- **ALWAYS** follow the core principles (KISS, YAGNI, etc.)
- **ALWAYS** implement proper error handling and logging

## Git Workflow

```bash
# Before committing, always run:
black .                         # Format code
ruff check .                    # Lint code
mypy .                         # Type checking
python -m pytest tests/        # Run tests

# Commit with descriptive messages
git add .
git commit -m "feat: add Snowflake MCP tool for database queries"
```

## Quick Reference

### Adding New MCP Tools

1. **Create tool handler** in appropriate module with Pydantic validation
2. **Implement proper error handling** using standard response functions
3. **Register tool** in main MCP server
4. **Add tests** for both success and failure cases
5. **Update documentation** if needed

### Example Tool Implementation

```python
from mcp.server.models import Tool
from pydantic import BaseModel

class ListTablesSchema(BaseModel):
    database: str = None
    schema: str = None

@server.tool("list_tables")
async def list_tables(arguments: dict) -> dict:
    """List all tables in Snowflake database"""
    try:
        # Validate input
        params = ListTablesSchema(**arguments)
        
        # Execute operation
        with get_snowflake_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
        
        return create_success_response(
            "Tables retrieved successfully",
            [dict(zip([col[0] for col in cursor.description], row)) for row in tables]
        )
        
    except Exception as error:
        return create_error_response(f"Failed to list tables: {str(error)}")
```

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.