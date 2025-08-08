# PRP: Snowflake MCP Server with Open WebUI Integration and Cortex SQL Generation

## Goal

Build a comprehensive Python-based MCP (Model Context Protocol) server that integrates with Snowflake and Open WebUI, leveraging Snowflake Cortex's SQL generation capabilities for natural language querying with security constraints. The server will provide both direct Snowflake access tools and natural language-powered tools that use Cortex to generate SQL from user queries.

This implementation follows the "fewer, more powerful tools" philosophy - instead of creating dozens of specific query tools, we create one primary natural language tool per view that leverages Cortex for flexibility while maintaining security through multi-layered validation.

## Context

### Current Project Architecture

The project is structured as a Python-based MCP server with the following key components already established:

**Existing Reference Implementation (`examples/` directory):**
- `examples/auth/snowflake_auth.py` - RSA private key authentication patterns
- `examples/auth/snowflake_auth_secure.py` - Production GCP Secret Manager integration  
- `examples/server/mcp_server.py` - MCP server with authentication framework
- `examples/cortex/cortex_generator.py` - Cortex SQL generation implementation
- `examples/tools/natural_language_tool.py` - Natural language tool architecture
- `examples/validators/sql_validator.py` - Security validation patterns
- `auth/snowflake_key.pem` - Current snowflake key

**Snowflake Environment (Available via MCP tools):**
- **Database:** PF
- **Schema:** BI  
- **Key View:** V_CREATOR_PAYMENTS_UNION with columns:
  - CREATOR_NAME (TEXT)
  - CAMPAIGN_NAME (TEXT)
  - PAYMENT_TYPE (TEXT)
  - COMPANY_NAME (TEXT)
  - PAYMENT_AMOUNT (NUMBER)
  - STRIPE_CUSTOMER_ID (TEXT)
  - REFERENCE_ID (TEXT)
  - CREATED_DATE (TIMESTAMP_NTZ)
  - STRIPE_CONNECTED_ACCOUNT_ID (TEXT)
  - PAYMENT_DATE (TIMESTAMP_NTZ)
  - STRIPE_CUSTOMER_NAME (TEXT)
  - STRIPE_CONNECTED_ACCOUNT_NAME (TEXT)
  - REFERENCE_TYPE (TEXT)
  - USER_ID (NUMBER)
  - PAYMENT_STATUS (TEXT)

**Existing AI Infrastructure Tables:**
- AI_USER_ACTIVITY_LOG - Enhanced for Cortex tracking
- AI_CORTEX_USAGE_LOG - Cortex credit usage tracking
- AI_SCHEMA_METADATA - Enhanced Cortex understanding
- AI_BUSINESS_CONTEXT - Guide Cortex generation

**Open WebUI Integration Requirements:**
- Bearer token authentication for external tool access
- MCP protocol compliance for tool registration
- Static tool registration with dynamic behavior via Cortex
- Integration via Open WebUI's tool management interface

**Deployment Architecture:**
- Local development with `.env` files
- Production deployment on GCP with Secret Manager
- Environment toggling via `ENVIRONMENT` variable
- RSA key-pair authentication for Snowflake (no MFA)

### Key Architectural Principles

**Static Registration + Dynamic Behavior:**
- Tools are registered once in Open WebUI's UI (static)
- Each tool uses Cortex to handle diverse queries (dynamic)
- Reduces cognitive load on LLM while providing powerful functionality

**Security Through Validation:**
- Open WebUI bearer token authentication required
- Cortex generates SQL with predefined constraints
- Post-generation SQL validation ensures only safe queries execute
- Full audit trail with natural language → SQL → results

**Fewer, More Powerful Tools:**
- One `query_payments` tool replaces dozens of specific query tools
- Natural language is the universal interface
- Cortex provides flexibility for new query patterns without code changes

## Implementation Blueprint

### Phase 1: Core Infrastructure Setup

#### Task 1.1: Environment and Dependencies Setup
**Input:** Project requirements and existing examples
**Output:** Properly configured Python environment with all dependencies

**Implementation Steps:**
1. Create `requirements.txt` with core dependencies:
   ```python
   # MCP and Web Framework
   mcp>=1.0.0
   fastapi>=0.104.0
   uvicorn[standard]>=0.24.0
   pydantic>=2.5.0
   
   # Snowflake Integration
   snowflake-connector-python[pandas]>=3.5.0
   cryptography>=41.0.0
   
   # Google Cloud Platform
   google-cloud-secret-manager>=2.16.0
   
   # Utilities
   python-dotenv>=1.0.0
   aiohttp>=3.8.0
   asyncio
   
   # Development and Testing
   pytest>=7.4.0
   pytest-asyncio>=0.21.0
   black>=23.0.0
   ruff>=0.1.0
   mypy>=1.7.0
   ```

2. Create `.env.example` template:
   ```bash
   # Environment Configuration
   ENVIRONMENT=local
   
   # Snowflake Configuration
   SNOWFLAKE_USER=SVC_POPFLY_APP
    SNOWFLAKE_PRIVATE_KEY_PATH=auth/snowflake_key.pem
    SNOWFLAKE_ACCOUNT=YCWWTPD-XA25231
    SNOWFLAKE_WAREHOUSE=COMPUTE_WH
    SNOWFLAKE_ROLE=ACCOUNTADMIN
    SNOWFLAKE_DATABASE=PF
    SNOWFLAKE_SCHEMA=BI
   
   
   # Open WebUI Integration
   OPEN_WEBUI_API_KEY=your-api-key
   
   # GCP Configuration (Production)
   GCP_PROJECT_ID=your-project-id
   
   # Cortex Configuration
   CORTEX_MODEL=llama3.1-70b
   CORTEX_TIMEOUT=30
   CORTEX_MAX_TOKENS=3000
   
   # Application Configuration
   MAX_QUERY_ROWS=1000
   MAX_QUERY_ROWS_LIMIT=10000
   QUERY_TIMEOUT=30
   ```

3. Create directory structure following the established pattern:
   ```
   /
   ├── auth/                    # Snowflake authentication
   ├── server/                  # MCP server implementation
   ├── cortex/                  # Cortex integration
   ├── tools/                   # MCP tools
   ├── validators/              # Security validation
   ├── auth_middleware/         # Open WebUI authentication
   ├── utils/                   # Utilities
   ├── config/                  # Configuration
   ├── initialsetup/           # Database setup
   └── tests/                  # Test suite
   ```

**Validation Gate:** 
- Virtual environment created and activated
- All dependencies installed successfully
- Directory structure matches specification
- `.env` file created from template

#### Task 1.2: Snowflake Authentication Module
**Input:** RSA private key and connection parameters
**Output:** Reliable Snowflake connection with RSA authentication

**Implementation Steps:**
1. Implement `auth/snowflake_auth.py` (copy patterns from `examples/auth/snowflake_auth.py`):
   ```python
   import snowflake.connector
   from cryptography.hazmat.primitives import serialization
   from cryptography.hazmat.primitives.serialization import load_pem_private_key
   import os
   from typing import Optional
   
   def get_snowflake_connection(
       account: str,
       user: str,
       private_key_path: str,
       private_key_passphrase: Optional[str] = None,
       database: Optional[str] = None,
       schema: Optional[str] = None,
       warehouse: Optional[str] = None
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

2. Implement `auth/snowflake_auth_secure.py` for production with GCP Secret Manager (copy from `examples/auth/snowflake_auth_secure.py`)

3. Implement `auth/secret_manager.py` for centralized secret management (copy from `examples/auth/secret_manager.py`)

**Validation Gate:**
- Successfully connect to Snowflake using RSA key authentication
- Connection works with both local file and GCP Secret Manager
- Basic query execution (SELECT 1) succeeds
- Connection cleanup handled properly

#### Task 1.3: Environment Configuration Management  
**Input:** Environment variables and GCP integration requirements
**Output:** Environment-aware configuration system

**Implementation Steps:**
1. Implement `config/settings.py`:
   ```python
   import os
   from typing import Optional
   from pydantic import BaseSettings
   from dotenv import load_dotenv
   
   load_dotenv()
   
   class Settings(BaseSettings):
       # Environment
       environment: str = os.getenv('ENVIRONMENT', 'local')
       
       # Snowflake Configuration
       snowflake_account: str = os.getenv('SNOWFLAKE_ACCOUNT', '')
       snowflake_user: str = os.getenv('SNOWFLAKE_USER', '')
       snowflake_private_key_path: str = os.getenv('SNOWFLAKE_PRIVATE_KEY_PATH', '')
       snowflake_private_key_passphrase: Optional[str] = os.getenv('SNOWFLAKE_PRIVATE_KEY_PASSPHRASE')
       snowflake_database: str = os.getenv('SNOWFLAKE_DATABASE', 'PF')
       snowflake_schema: str = os.getenv('SNOWFLAKE_SCHEMA', 'BI')
       snowflake_warehouse: str = os.getenv('SNOWFLAKE_WAREHOUSE', 'COMPUTE_WH')
       
       # Open WebUI
       open_webui_api_key: str = os.getenv('OPEN_WEBUI_API_KEY', '')
       
       # Cortex Configuration
       cortex_model: str = os.getenv('CORTEX_MODEL', 'llama3.1-70b')
       cortex_timeout: int = int(os.getenv('CORTEX_TIMEOUT', '30'))
       cortex_max_tokens: int = int(os.getenv('CORTEX_MAX_TOKENS', '3000'))
       
       # Query Configuration
       max_query_rows: int = int(os.getenv('MAX_QUERY_ROWS', '1000'))
       max_query_rows_limit: int = int(os.getenv('MAX_QUERY_ROWS_LIMIT', '10000'))
       query_timeout: int = int(os.getenv('QUERY_TIMEOUT', '30'))
       
       # GCP Configuration
       gcp_project_id: Optional[str] = os.getenv('GCP_PROJECT_ID')
       
       def validate_required_settings(self) -> bool:
           """Validate that all required settings are present"""
           required_local = [
               'snowflake_account', 'snowflake_user', 'snowflake_private_key_path', 
               'open_webui_api_key'
           ]
           
           if self.environment == 'production':
               required_local.append('gcp_project_id')
           
           missing = [field for field in required_local if not getattr(self, field)]
           
           if missing:
               raise ValueError(f"Missing required settings: {missing}")
           
           return True
   
   settings = Settings()
   ```

2. Implement `utils/config.py` for environment switching (copy from `examples/config/environment_config.py`)

**Validation Gate:**
- Settings load correctly from environment variables
- Environment switching works (local vs production)
- Required settings validation works
- GCP Secret Manager integration functional in production mode

### Phase 2: MCP Server Infrastructure

#### Task 2.1: Bearer Token Authentication Middleware
**Input:** Open WebUI bearer token requirements
**Output:** Secure authentication middleware for MCP server

**Implementation Steps:**
1. Implement `auth_middleware/bearer_auth.py` (copy from `examples/auth_middleware/bearer_auth.py`):
   ```python
   from fastapi import HTTPException, Depends
   from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
   from config.settings import settings
   import logging
   
   security = HTTPBearer()
   
   def validate_bearer_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
       """Validate bearer token from Open WebUI"""
       if not settings.open_webui_api_key:
           logging.error("OPEN_WEBUI_API_KEY not configured")
           raise HTTPException(status_code=500, detail="Server configuration error")
       
       if credentials.credentials != settings.open_webui_api_key:
           logging.warning(f"Invalid bearer token attempt: {credentials.credentials[:10]}...")
           raise HTTPException(status_code=401, detail="Invalid bearer token")
       
       return credentials.credentials
   ```

**Validation Gate:**
- Bearer token validation works correctly
- Invalid tokens are rejected with 401
- Missing configuration raises 500 error
- Security logging captures authentication attempts

#### Task 2.2: Core MCP Server Implementation
**Input:** MCP protocol requirements and authentication framework
**Output:** Functioning MCP server with tool registration capabilities

**Implementation Steps:**
1. Implement `server/mcp_server.py` (following patterns from `examples/server/mcp_server.py`):
   ```python
   import asyncio
   import logging
   from typing import Any, Dict
   from mcp.server import Server
   from mcp.server.models import InitializationOptions
   from mcp.server.stdio import stdio_server
   from mcp.types import TextContent, Tool
   
   from config.settings import settings
   from auth.snowflake_auth import get_snowflake_connection
   from tools.snowflake_tools import register_snowflake_tools
   from tools.cortex_tools import register_cortex_tools
   from utils.logging import setup_logging
   
   class SnowflakeMCP:
       def __init__(self):
           self.server = Server("Snowflake MCP Server")
           self.setup_logging()
           
       def setup_logging(self):
           """Configure logging for the MCP server"""
           logging.basicConfig(
               level=logging.INFO,
               format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
           )
           self.logger = logging.getLogger(__name__)
           
       async def init(self):
           """Initialize the MCP server with tools and resources"""
           try:
               # Validate configuration
               settings.validate_required_settings()
               
               # Test Snowflake connection
               await self.test_snowflake_connection()
               
               # Register tools
               register_snowflake_tools(self.server)
               register_cortex_tools(self.server)
               
               # Register resources
               self.register_resources()
               
               self.logger.info("Snowflake MCP Server initialized successfully")
               
           except Exception as error:
               self.logger.error(f"Failed to initialize MCP server: {error}")
               raise
       
       async def test_snowflake_connection(self):
           """Test Snowflake connectivity during startup"""
           try:
               conn = get_snowflake_connection(
                   account=settings.snowflake_account,
                   user=settings.snowflake_user,
                   private_key_path=settings.snowflake_private_key_path,
                   private_key_passphrase=settings.snowflake_private_key_passphrase,
                   database=settings.snowflake_database,
                   schema=settings.snowflake_schema,
                   warehouse=settings.snowflake_warehouse
               )
               
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
                   InitializationOptions()
               )
               
       except KeyboardInterrupt:
           logging.info("Server shutdown requested")
       except Exception as error:
           logging.error(f"Server error: {error}")
           raise
   
   if __name__ == "__main__":
       asyncio.run(main())
   ```

**Validation Gate:**
- MCP server starts without errors
- Snowflake connection test passes during startup
- Server responds to basic MCP protocol requests
- Logging output shows successful initialization

### Phase 3: SQL Validation and Security

#### Task 3.1: SQL Validation System
**Input:** Security requirements and SQL injection prevention needs
**Output:** Comprehensive SQL validation system

**Implementation Steps:**
1. Implement `validators/sql_validator.py` (copy from `examples/validators/sql_validator.py`):
   ```python
   import re
   from typing import Dict, List, Set
   from pydantic import BaseModel
   
   class SqlValidationResult(BaseModel):
       is_valid: bool
       error: str = None
       warnings: List[str] = []
   
   class SqlValidator:
       """SQL validation system for security and compliance"""
       
       DANGEROUS_PATTERNS = [
           r'DROP\s+TABLE',
           r'DELETE\s+FROM',
           r'TRUNCATE\s+TABLE',
           r'ALTER\s+TABLE',
           r'CREATE\s+TABLE',
           r'INSERT\s+INTO',
           r'UPDATE\s+.*SET',
           r'GRANT\s+',
           r'REVOKE\s+',
           r'EXEC\s+',
           r'EXECUTE\s+',
           r'xp_\w+',
           r'sp_\w+',
           r';\s*DROP',
           r';\s*DELETE',
           r'UNION\s+.*SELECT.*--',
           r'1\s*=\s*1',
           r'\'.*OR.*\'.*=.*\'',
       ]
       
       READ_ONLY_KEYWORDS = ['SELECT', 'SHOW', 'DESCRIBE', 'EXPLAIN', 'WITH']
       
       ALLOWED_TABLES = {
           'V_CREATOR_PAYMENTS_UNION',
           'AI_USER_ACTIVITY_LOG',
           'AI_BUSINESS_CONTEXT',
           'AI_SCHEMA_METADATA'
       }
       
       ALLOWED_COLUMNS_V_CREATOR_PAYMENTS = {
           'CREATOR_NAME', 'CAMPAIGN_NAME', 'PAYMENT_TYPE', 'COMPANY_NAME',
           'PAYMENT_AMOUNT', 'STRIPE_CUSTOMER_ID', 'REFERENCE_ID', 
           'CREATED_DATE', 'STRIPE_CONNECTED_ACCOUNT_ID', 'PAYMENT_DATE',
           'STRIPE_CUSTOMER_NAME', 'STRIPE_CONNECTED_ACCOUNT_NAME',
           'REFERENCE_TYPE', 'USER_ID', 'PAYMENT_STATUS'
       }
   
       @classmethod
       def validate_sql_query(cls, sql: str) -> SqlValidationResult:
           """Comprehensive SQL query validation"""
           sql_upper = sql.upper().strip()
           
           # Check for dangerous patterns
           for pattern in cls.DANGEROUS_PATTERNS:
               if re.search(pattern, sql_upper, re.IGNORECASE):
                   return SqlValidationResult(
                       is_valid=False,
                       error=f"Dangerous SQL operation detected: {pattern}"
                   )
           
           # Verify it's a read-only operation
           if not cls.is_read_only_query(sql):
               return SqlValidationResult(
                   is_valid=False,
                   error="Only read-only operations (SELECT, SHOW, DESCRIBE) are allowed"
               )
           
           # Validate table access
           table_validation = cls.validate_table_access(sql)
           if not table_validation.is_valid:
               return table_validation
           
           return SqlValidationResult(is_valid=True)
   
       @classmethod
       def is_read_only_query(cls, sql: str) -> bool:
           """Check if SQL query is read-only"""
           sql_upper = sql.strip().upper()
           return any(sql_upper.startswith(keyword) for keyword in cls.READ_ONLY_KEYWORDS)
   
       @classmethod
       def validate_table_access(cls, sql: str) -> SqlValidationResult:
           """Validate that query only accesses allowed tables"""
           # Extract table names from SQL (simplified approach)
           sql_upper = sql.upper()
           
           # Look for FROM and JOIN clauses
           table_references = re.findall(r'FROM\s+(\w+)', sql_upper)
           table_references.extend(re.findall(r'JOIN\s+(\w+)', sql_upper))
           
           # Check if any referenced table is not in allowed list
           for table in table_references:
               if table not in cls.ALLOWED_TABLES:
                   return SqlValidationResult(
                       is_valid=False,
                       error=f"Access to table '{table}' is not allowed. Allowed tables: {', '.join(cls.ALLOWED_TABLES)}"
                   )
           
           return SqlValidationResult(is_valid=True)
   
       @classmethod
       def format_database_error(cls, error: Exception) -> str:
           """Format database error for safe client consumption"""
           error_str = str(error).lower()
           
           if "connection" in error_str:
               return "Database connection error"
           elif "permission" in error_str or "access" in error_str:
               return "Database permission error"
           elif "timeout" in error_str:
               return "Database query timeout"
           elif "syntax" in error_str:
               return "SQL syntax error"
           else:
               return "Database operation failed"
   ```

**Validation Gate:**
- SQL validation correctly identifies dangerous patterns
- Read-only validation works for SELECT/SHOW/DESCRIBE statements
- Table access validation allows only whitelisted tables
- Error formatting sanitizes internal database details

#### Task 3.2: Cortex SQL Generation Module
**Input:** Natural language queries and business context
**Output:** Secure SQL generation using Snowflake Cortex

**Implementation Steps:**
1. Implement `cortex/cortex_generator.py` (copy from `examples/cortex/cortex_generator.py`):
   ```python
   import asyncio
   import logging
   from typing import Dict, Any, Optional, List
   from pydantic import BaseModel
   import json
   
   from auth.snowflake_auth import get_snowflake_connection
   from config.settings import settings
   from validators.sql_validator import SqlValidator, SqlValidationResult
   from utils.logging import log_cortex_usage
   
   class CortexRequest(BaseModel):
       natural_language_query: str
       view_name: str = "V_CREATOR_PAYMENTS_UNION"
       max_rows: int = 1000
       context: Optional[Dict[str, Any]] = None
   
   class CortexResponse(BaseModel):
       success: bool
       generated_sql: Optional[str] = None
       validation_result: Optional[SqlValidationResult] = None
       error: Optional[str] = None
       cortex_credits_used: Optional[float] = None
   
   class CortexGenerator:
       """Snowflake Cortex SQL generation with security validation"""
       
       VIEW_CONSTRAINTS = {
           "V_CREATOR_PAYMENTS_UNION": {
               "allowed_operations": ["SELECT", "WHERE", "GROUP BY", "ORDER BY", "LIMIT", "HAVING"],
               "allowed_columns": [
                   "CREATOR_NAME", "CAMPAIGN_NAME", "PAYMENT_TYPE", "COMPANY_NAME",
                   "PAYMENT_AMOUNT", "STRIPE_CUSTOMER_ID", "REFERENCE_ID", 
                   "CREATED_DATE", "STRIPE_CONNECTED_ACCOUNT_ID", "PAYMENT_DATE",
                   "STRIPE_CUSTOMER_NAME", "STRIPE_CONNECTED_ACCOUNT_NAME",
                   "REFERENCE_TYPE", "USER_ID", "PAYMENT_STATUS"
               ],
               "forbidden_keywords": ["DROP", "DELETE", "UPDATE", "INSERT", "CREATE", "ALTER"],
               "business_context": {
                   "purpose": "Creator payment tracking and analysis",
                   "key_relationships": "Payments linked to creators, campaigns, and companies",
                   "common_filters": "payment_status, payment_date, creator_name, campaign_name"
               }
           }
       }
   
       @classmethod
       async def generate_sql(cls, request: CortexRequest) -> CortexResponse:
           """Generate SQL using Snowflake Cortex with validation"""
           try:
               # Get view constraints
               constraints = cls.VIEW_CONSTRAINTS.get(request.view_name)
               if not constraints:
                   return CortexResponse(
                       success=False,
                       error=f"View '{request.view_name}' not configured for Cortex generation"
                   )
               
               # Build Cortex prompt
               prompt = cls.build_cortex_prompt(request, constraints)
               
               # Execute Cortex SQL generation
               generated_sql = await cls.call_cortex_complete(prompt)
               
               # Validate generated SQL
               validation_result = SqlValidator.validate_sql_query(generated_sql)
               
               # Log usage
               await log_cortex_usage(
                   natural_query=request.natural_language_query,
                   generated_sql=generated_sql,
                   validation_passed=validation_result.is_valid,
                   view_name=request.view_name
               )
               
               return CortexResponse(
                   success=validation_result.is_valid,
                   generated_sql=generated_sql,
                   validation_result=validation_result,
                   error=validation_result.error if not validation_result.is_valid else None
               )
               
           except Exception as error:
               logging.error(f"Cortex generation failed: {error}")
               return CortexResponse(
                   success=False,
                   error=f"SQL generation failed: {str(error)}"
               )
   
       @classmethod
       def build_cortex_prompt(cls, request: CortexRequest, constraints: Dict[str, Any]) -> str:
           """Build optimized prompt for Cortex SQL generation"""
           
           columns_desc = ", ".join(constraints["allowed_columns"])
           allowed_ops = ", ".join(constraints["allowed_operations"])
           business_context = constraints["business_context"]
           
           prompt = f"""
   You are a SQL expert generating queries for the {request.view_name} view in Snowflake.
   
   **STRICT REQUIREMENTS:**
   1. Generate ONLY SELECT statements
   2. Use ONLY these columns: {columns_desc}
   3. Use ONLY these operations: {allowed_ops}
   4. Always include LIMIT clause (max {request.max_rows} rows)
   5. Use proper Snowflake SQL syntax
   6. No subqueries, CTEs, or complex joins
   
   **View Context:**
   - Purpose: {business_context['purpose']}
   - Key relationships: {business_context['key_relationships']}
   - Common filters: {business_context['common_filters']}
   
   **Column Data Types:**
   - CREATOR_NAME, CAMPAIGN_NAME, PAYMENT_TYPE, COMPANY_NAME: TEXT
   - STRIPE_CUSTOMER_ID, REFERENCE_ID, STRIPE_CONNECTED_ACCOUNT_ID: TEXT
   - STRIPE_CUSTOMER_NAME, STRIPE_CONNECTED_ACCOUNT_NAME, REFERENCE_TYPE: TEXT
   - PAYMENT_AMOUNT, USER_ID: NUMBER
   - CREATED_DATE, PAYMENT_DATE: TIMESTAMP_NTZ
   - PAYMENT_STATUS: TEXT (values: PAID, PENDING, FAILED, etc.)
   
   **Natural Language Query:** {request.natural_language_query}
   
   Generate a single, executable SQL SELECT statement that answers the query:
   """
           
           return prompt.strip()
   
       @classmethod
       async def call_cortex_complete(cls, prompt: str) -> str:
           """Call Snowflake Cortex COMPLETE function"""
           try:
               conn = get_snowflake_connection(
                   account=settings.snowflake_account,
                   user=settings.snowflake_user,
                   private_key_path=settings.snowflake_private_key_path,
                   private_key_passphrase=settings.snowflake_private_key_passphrase,
                   database=settings.snowflake_database,
                   schema=settings.snowflake_schema,
                   warehouse=settings.snowflake_warehouse
               )
               
               cursor = conn.cursor()
               
               # Execute Cortex COMPLETE function
               cortex_sql = f"""
               SELECT SNOWFLAKE.CORTEX.COMPLETE(
                   '{settings.cortex_model}',
                   %s,
                   {{
                       'max_tokens': {settings.cortex_max_tokens},
                       'temperature': 0.1
                   }}
               ) as generated_sql
               """
               
               cursor.execute(cortex_sql, (prompt,))
               result = cursor.fetchone()
               
               cursor.close()
               conn.close()
               
               if result and result[0]:
                   # Extract SQL from Cortex response (may need parsing)
                   generated_sql = str(result[0]).strip()
                   
                   # Clean up common Cortex response formatting
                   if generated_sql.startswith('```sql'):
                       generated_sql = generated_sql.replace('```sql', '').replace('```', '')
                   
                   return generated_sql.strip()
               else:
                   raise ValueError("Cortex returned empty response")
               
           except Exception as error:
               logging.error(f"Cortex COMPLETE call failed: {error}")
               raise
   ```

**Validation Gate:**
- Cortex generates valid SQL from natural language queries
- Generated SQL passes security validation
- View constraints are properly enforced
- Cortex usage is logged for monitoring

### Phase 4: MCP Tools Implementation

#### Task 4.1: Direct Snowflake Tools
**Input:** Snowflake MCP tools requirements matching existing patterns
**Output:** Core Snowflake database access tools

**Implementation Steps:**
1. Implement `tools/snowflake_tools.py`:
   ```python
   import json
   import logging
   from typing import Dict, Any
   from mcp.server import Server
   from pydantic import BaseModel, validator
   
   from auth.snowflake_auth import get_snowflake_connection
   from config.settings import settings
   from validators.sql_validator import SqlValidator
   from utils.response_helpers import create_success_response, create_error_response
   from utils.logging import log_activity
   
   # Pydantic schemas for input validation
   class ListDatabasesSchema(BaseModel):
       pass
   
   class ListSchemasSchema(BaseModel):
       database: str
       
       @validator('database')
       def validate_database(cls, v):
           if not v.strip():
               raise ValueError("Database name cannot be empty")
           return v.strip().upper()
   
   class ListTablesSchema(BaseModel):
       database: str
       schema: str
       
       @validator('database', 'schema')
       def validate_names(cls, v):
           if not v.strip():
               raise ValueError("Database and schema names cannot be empty")
           return v.strip().upper()
   
   class DescribeTableSchema(BaseModel):
       table_name: str
       
       @validator('table_name')
       def validate_table_name(cls, v):
           if not v.strip():
               raise ValueError("Table name cannot be empty")
           # Expected format: database.schema.table
           parts = v.strip().split('.')
           if len(parts) != 3:
               raise ValueError("Table name must be in format 'database.schema.table'")
           return v.strip().upper()
   
   class ReadQuerySchema(BaseModel):
       query: str
       max_rows: int = 1000
       
       @validator('query')
       def validate_query(cls, v):
           if not v.strip():
               raise ValueError("Query cannot be empty")
           
           # Basic validation - more detailed validation happens later
           sql_upper = v.strip().upper()
           if not sql_upper.startswith('SELECT'):
               raise ValueError("Only SELECT queries are allowed")
           
           return v.strip()
       
       @validator('max_rows')
       def validate_max_rows(cls, v):
           if v <= 0 or v > settings.max_query_rows_limit:
               raise ValueError(f"max_rows must be between 1 and {settings.max_query_rows_limit}")
           return v
   
   class AppendInsightSchema(BaseModel):
       insight: str
       
       @validator('insight')
       def validate_insight(cls, v):
           if not v.strip():
               raise ValueError("Insight cannot be empty")
           if len(v) > 5000:
               raise ValueError("Insight must be less than 5000 characters")
           return v.strip()
   
   def register_snowflake_tools(server: Server):
       """Register direct Snowflake access tools"""
       
       @server.tool("list_databases")
       async def list_databases(arguments: Dict[str, Any]) -> Dict[str, Any]:
           """List all available databases in Snowflake"""
           try:
               # Validate input
               ListDatabasesSchema(**arguments)
               
               conn = get_snowflake_connection(
                   account=settings.snowflake_account,
                   user=settings.snowflake_user,
                   private_key_path=settings.snowflake_private_key_path,
                   private_key_passphrase=settings.snowflake_private_key_passphrase,
                   warehouse=settings.snowflake_warehouse
               )
               
               cursor = conn.cursor()
               cursor.execute("SHOW DATABASES")
               databases = cursor.fetchall()
               
               # Convert to list of dictionaries
               database_list = []
               for db in databases:
                   database_list.append({
                       "DATABASE_NAME": db[1]  # Database name is in second column
                   })
               
               cursor.close()
               conn.close()
               
               await log_activity("list_databases", arguments, len(database_list))
               
               return create_success_response(
                   f"Found {len(database_list)} databases",
                   database_list
               )
               
           except Exception as error:
               logging.error(f"list_databases error: {error}")
               return create_error_response(f"Failed to list databases: {str(error)}")
       
       @server.tool("list_schemas")  
       async def list_schemas(arguments: Dict[str, Any]) -> Dict[str, Any]:
           """List all schemas in a specific database"""
           try:
               # Validate input
               params = ListSchemasSchema(**arguments)
               
               conn = get_snowflake_connection(
                   account=settings.snowflake_account,
                   user=settings.snowflake_user,
                   private_key_path=settings.snowflake_private_key_path,
                   private_key_passphrase=settings.snowflake_private_key_passphrase,
                   database=params.database,
                   warehouse=settings.snowflake_warehouse
               )
               
               cursor = conn.cursor()
               cursor.execute(f"SHOW SCHEMAS IN DATABASE {params.database}")
               schemas = cursor.fetchall()
               
               # Convert to list of dictionaries
               schema_list = []
               for schema in schemas:
                   schema_list.append({
                       "SCHEMA_NAME": schema[1]  # Schema name is in second column
                   })
               
               cursor.close()
               conn.close()
               
               await log_activity("list_schemas", arguments, len(schema_list))
               
               return create_success_response(
                   f"Found {len(schema_list)} schemas in database {params.database}",
                   schema_list
               )
               
           except Exception as error:
               logging.error(f"list_schemas error: {error}")
               return create_error_response(f"Failed to list schemas: {str(error)}")
       
       @server.tool("list_tables")
       async def list_tables(arguments: Dict[str, Any]) -> Dict[str, Any]:
           """List all tables in a specific database and schema"""
           try:
               # Validate input
               params = ListTablesSchema(**arguments)
               
               conn = get_snowflake_connection(
                   account=settings.snowflake_account,
                   user=settings.snowflake_user,
                   private_key_path=settings.snowflake_private_key_path,
                   private_key_passphrase=settings.snowflake_private_key_passphrase,
                   database=params.database,
                   schema=params.schema,
                   warehouse=settings.snowflake_warehouse
               )
               
               cursor = conn.cursor()
               cursor.execute(f"SHOW TABLES IN SCHEMA {params.database}.{params.schema}")
               tables = cursor.fetchall()
               
               # Convert to list of dictionaries with more detail
               table_list = []
               for table in tables:
                   table_list.append({
                       "TABLE_CATALOG": params.database,
                       "TABLE_SCHEMA": params.schema,
                       "TABLE_NAME": table[1],  # Table name is in second column
                       "COMMENT": table[6] if len(table) > 6 else None  # Comment column
                   })
               
               cursor.close()
               conn.close()
               
               await log_activity("list_tables", arguments, len(table_list))
               
               return create_success_response(
                   f"Found {len(table_list)} tables in {params.database}.{params.schema}",
                   table_list
               )
               
           except Exception as error:
               logging.error(f"list_tables error: {error}")
               return create_error_response(f"Failed to list tables: {str(error)}")
       
       @server.tool("describe_table")
       async def describe_table(arguments: Dict[str, Any]) -> Dict[str, Any]:
           """Get detailed schema information for a specific table"""
           try:
               # Validate input
               params = DescribeTableSchema(**arguments)
               
               conn = get_snowflake_connection(
                   account=settings.snowflake_account,
                   user=settings.snowflake_user,
                   private_key_path=settings.snowflake_private_key_path,
                   private_key_passphrase=settings.snowflake_private_key_passphrase,
                   warehouse=settings.snowflake_warehouse
               )
               
               cursor = conn.cursor()
               cursor.execute(f"DESCRIBE TABLE {params.table_name}")
               columns = cursor.fetchall()
               
               # Convert to list of dictionaries
               column_list = []
               for col in columns:
                   column_list.append({
                       "COLUMN_NAME": col[0],
                       "DATA_TYPE": col[1], 
                       "IS_NULLABLE": "YES" if col[2] else "NO",
                       "COLUMN_DEFAULT": col[3],
                       "COMMENT": col[7] if len(col) > 7 else None
                   })
               
               cursor.close()
               conn.close()
               
               await log_activity("describe_table", arguments, len(column_list))
               
               return create_success_response(
                   f"Table {params.table_name} has {len(column_list)} columns",
                   column_list
               )
               
           except Exception as error:
               logging.error(f"describe_table error: {error}")
               return create_error_response(f"Failed to describe table: {str(error)}")
       
       @server.tool("read_query")
       async def read_query(arguments: Dict[str, Any]) -> Dict[str, Any]:
           """Execute a read-only SQL query against Snowflake"""
           try:
               # Validate input
               params = ReadQuerySchema(**arguments)
               
               # Validate SQL query for security
               validation = SqlValidator.validate_sql_query(params.query)
               if not validation.is_valid:
                   return create_error_response(f"Invalid SQL query: {validation.error}")
               
               conn = get_snowflake_connection(
                   account=settings.snowflake_account,
                   user=settings.snowflake_user,
                   private_key_path=settings.snowflake_private_key_path,
                   private_key_passphrase=settings.snowflake_private_key_passphrase,
                   database=settings.snowflake_database,
                   schema=settings.snowflake_schema,
                   warehouse=settings.snowflake_warehouse
               )
               
               cursor = conn.cursor()
               
               # Add LIMIT clause if not present
               limited_query = params.query
               if "LIMIT" not in limited_query.upper():
                   limited_query += f" LIMIT {params.max_rows}"
               
               cursor.execute(limited_query)
               results = cursor.fetchall()
               column_names = [desc[0] for desc in cursor.description]
               
               # Convert to list of dictionaries
               result_list = []
               for row in results:
                   result_dict = {}
                   for i, value in enumerate(row):
                       result_dict[column_names[i]] = value
                   result_list.append(result_dict)
               
               cursor.close()
               conn.close()
               
               await log_activity("read_query", {"query": params.query}, len(result_list))
               
               return create_success_response(
                   f"Query executed successfully. {len(result_list)} rows returned.",
                   {
                       "query": limited_query,
                       "results": result_list,
                       "row_count": len(result_list)
                   }
               )
               
           except Exception as error:
               logging.error(f"read_query error: {error}")
               return create_error_response(f"Query execution failed: {SqlValidator.format_database_error(error)}")
       
       @server.tool("append_insight")
       async def append_insight(arguments: Dict[str, Any]) -> Dict[str, Any]:
           """Add a data insight to the insights memo"""
           try:
               # Validate input
               params = AppendInsightSchema(**arguments)
               
               # For now, just return success - in production this would append to a memo resource
               await log_activity("append_insight", arguments, 1)
               
               return create_success_response(
                   "Insight recorded successfully",
                   {
                       "insight": params.insight,
                       "recorded_at": "memo://insights"
                   }
               )
               
           except Exception as error:
               logging.error(f"append_insight error: {error}")
               return create_error_response(f"Failed to record insight: {str(error)}")
   ```

**Validation Gate:**
- All tools successfully register with MCP server
- Input validation works for all parameter types
- Database connections work for each tool
- Error handling provides appropriate user feedback
- Activity logging captures tool usage

#### Task 4.2: Cortex-Powered Natural Language Tools
**Input:** Natural language query requirements and Cortex integration
**Output:** Natural language tools that generate SQL via Cortex

**Implementation Steps:**
1. Implement `tools/cortex_tools.py`:
   ```python
   import json
   import logging
   from typing import Dict, Any
   from mcp.server import Server
   from pydantic import BaseModel, validator
   
   from cortex.cortex_generator import CortexGenerator, CortexRequest
   from auth.snowflake_auth import get_snowflake_connection
   from config.settings import settings
   from utils.response_helpers import create_success_response, create_error_response
   from utils.logging import log_activity
   
   class QueryPaymentsSchema(BaseModel):
       query: str
       include_sql: bool = True
       max_rows: int = 1000
       
       @validator('query')
       def validate_query(cls, v):
           if not v.strip():
               raise ValueError("Query cannot be empty")
           if len(v) > 1000:
               raise ValueError("Query must be less than 1000 characters")
           return v.strip()
       
       @validator('max_rows')
       def validate_max_rows(cls, v):
           if v <= 0 or v > settings.max_query_rows_limit:
               raise ValueError(f"max_rows must be between 1 and {settings.max_query_rows_limit}")
           return v
   
   def register_cortex_tools(server: Server):
       """Register natural language tools powered by Cortex"""
       
       @server.tool("query_payments")
       async def query_payments(arguments: Dict[str, Any]) -> Dict[str, Any]:
           """Query creator payments using natural language. 
           
           This tool handles all payment-related questions including filtering by creator, 
           date, amount, status, campaign, and more using natural language queries that 
           are converted to SQL via Snowflake Cortex.
           
           Examples:
           - "Show me all payments to creators in the last 30 days"
           - "Find payments over $1000 that are still pending"  
           - "Which creators received payments for campaign X in January?"
           - "Total payments by month for creator John Smith"
           - "List failed payments with amounts over $500"
           """
           try:
               # Validate input
               params = QueryPaymentsSchema(**arguments)
               
               # Create Cortex request
               cortex_request = CortexRequest(
                   natural_language_query=params.query,
                   view_name="V_CREATOR_PAYMENTS_UNION",
                   max_rows=params.max_rows
               )
               
               # Generate SQL using Cortex
               cortex_response = await CortexGenerator.generate_sql(cortex_request)
               
               if not cortex_response.success:
                   return create_error_response(
                       f"SQL generation failed: {cortex_response.error}",
                       {
                           "natural_query": params.query,
                           "cortex_error": cortex_response.error
                       }
                   )
               
               # Execute the generated SQL
               try:
                   conn = get_snowflake_connection(
                       account=settings.snowflake_account,
                       user=settings.snowflake_user,
                       private_key_path=settings.snowflake_private_key_path,
                       private_key_passphrase=settings.snowflake_private_key_passphrase,
                       database=settings.snowflake_database,
                       schema=settings.snowflake_schema,
                       warehouse=settings.snowflake_warehouse
                   )
                   
                   cursor = conn.cursor()
                   cursor.execute(cortex_response.generated_sql)
                   results = cursor.fetchall()
                   column_names = [desc[0] for desc in cursor.description]
                   
                   # Convert to list of dictionaries
                   result_list = []
                   for row in results:
                       result_dict = {}
                       for i, value in enumerate(row):
                           result_dict[column_names[i]] = value
                       result_list.append(result_dict)
                   
                   cursor.close()
                   conn.close()
                   
                   # Log successful activity
                   await log_activity("query_payments", {
                       "natural_query": params.query,
                       "generated_sql": cortex_response.generated_sql
                   }, len(result_list))
                   
                   # Build response
                   response_data = {
                       "natural_query": params.query,
                       "results": result_list,
                       "row_count": len(result_list)
                   }
                   
                   if params.include_sql:
                       response_data["generated_sql"] = cortex_response.generated_sql
                   
                   success_message = f"Natural language query executed successfully. {len(result_list)} rows returned."
                   if params.include_sql:
                       success_message += f"\n\n**Generated SQL:**\n```sql\n{cortex_response.generated_sql}\n```"
                   
                   return create_success_response(success_message, response_data)
                   
               except Exception as db_error:
                   logging.error(f"Database execution error: {db_error}")
                   return create_error_response(
                       f"Query execution failed: {str(db_error)}",
                       {
                           "natural_query": params.query,
                           "generated_sql": cortex_response.generated_sql if params.include_sql else None,
                           "database_error": str(db_error)
                       }
                   )
               
           except Exception as error:
               logging.error(f"query_payments error: {error}")
               return create_error_response(f"Natural language query failed: {str(error)}")
   ```

**Validation Gate:**
- Natural language queries generate appropriate SQL
- Generated SQL executes successfully against Snowflake
- Results are properly formatted and returned
- Both successful and error cases are handled gracefully
- Generated SQL is optionally included in response for transparency

### Phase 5: Database Setup and Configuration

#### Task 5.1: Database Initialization Scripts
**Input:** AI table requirements and view constraints
**Output:** Complete database setup scripts

**Implementation Steps:**
1. Create `initialsetup/sql/01_create_ai_tables.sql`:
   ```sql
   -- Create AI tables for Cortex integration and validation
   -- Script: 01_create_ai_tables.sql
   
   USE DATABASE PF;
   USE SCHEMA BI;
   
   -- AI_VIEW_CONSTRAINTS: Security constraints for Cortex SQL generation
   CREATE TABLE IF NOT EXISTS AI_VIEW_CONSTRAINTS (
       ID INTEGER AUTOINCREMENT,
       VIEW_NAME VARCHAR(255) NOT NULL,
       ALLOWED_OPERATIONS TEXT NOT NULL, -- JSON array of allowed SQL operations
       ALLOWED_COLUMNS TEXT NOT NULL,    -- JSON array of allowed column names
       FORBIDDEN_KEYWORDS TEXT NOT NULL, -- JSON array of forbidden keywords
       MAX_ROWS_DEFAULT INTEGER DEFAULT 1000,
       MAX_ROWS_LIMIT INTEGER DEFAULT 10000,
       BUSINESS_CONTEXT TEXT,           -- JSON object with business context
       CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
       UPDATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
       CONSTRAINT AI_VIEW_CONSTRAINTS_PK PRIMARY KEY (ID),
       CONSTRAINT AI_VIEW_CONSTRAINTS_VIEW_NAME_UK UNIQUE (VIEW_NAME)
   );
   
   -- AI_CORTEX_PROMPTS: Optimized prompts for better SQL generation
   CREATE TABLE IF NOT EXISTS AI_CORTEX_PROMPTS (
       ID INTEGER AUTOINCREMENT,
       VIEW_NAME VARCHAR(255) NOT NULL,
       PROMPT_TYPE VARCHAR(100) NOT NULL, -- 'base', 'context', 'examples'
       PROMPT_TEMPLATE TEXT NOT NULL,
       USAGE_COUNT INTEGER DEFAULT 0,
       SUCCESS_RATE FLOAT DEFAULT 0.0,
       AVERAGE_TOKENS INTEGER DEFAULT 0,
       CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
       UPDATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
       CONSTRAINT AI_CORTEX_PROMPTS_PK PRIMARY KEY (ID),
       CONSTRAINT AI_CORTEX_PROMPTS_VIEW_TYPE_UK UNIQUE (VIEW_NAME, PROMPT_TYPE)
   );
   
   -- Indexes for performance
   CREATE INDEX IF NOT EXISTS AI_VIEW_CONSTRAINTS_VIEW_IDX ON AI_VIEW_CONSTRAINTS (VIEW_NAME);
   CREATE INDEX IF NOT EXISTS AI_CORTEX_PROMPTS_VIEW_IDX ON AI_CORTEX_PROMPTS (VIEW_NAME);
   CREATE INDEX IF NOT EXISTS AI_CORTEX_PROMPTS_TYPE_IDX ON AI_CORTEX_PROMPTS (PROMPT_TYPE);
   
   COMMIT;
   ```

2. Create `initialsetup/sql/02_insert_view_constraints.sql`:
   ```sql
   -- Insert security constraints for V_CREATOR_PAYMENTS_UNION
   -- Script: 02_insert_view_constraints.sql
   
   USE DATABASE PF;
   USE SCHEMA BI;
   
   -- Insert constraints for V_CREATOR_PAYMENTS_UNION
   INSERT INTO AI_VIEW_CONSTRAINTS (
       VIEW_NAME,
       ALLOWED_OPERATIONS,
       ALLOWED_COLUMNS,
       FORBIDDEN_KEYWORDS,
       MAX_ROWS_DEFAULT,
       MAX_ROWS_LIMIT,
       BUSINESS_CONTEXT
   ) VALUES (
       'V_CREATOR_PAYMENTS_UNION',
       '["SELECT", "WHERE", "GROUP BY", "ORDER BY", "LIMIT", "HAVING", "COUNT", "SUM", "AVG", "MIN", "MAX"]',
       '["CREATOR_NAME", "CAMPAIGN_NAME", "PAYMENT_TYPE", "COMPANY_NAME", "PAYMENT_AMOUNT", "STRIPE_CUSTOMER_ID", "REFERENCE_ID", "CREATED_DATE", "STRIPE_CONNECTED_ACCOUNT_ID", "PAYMENT_DATE", "STRIPE_CUSTOMER_NAME", "STRIPE_CONNECTED_ACCOUNT_NAME", "REFERENCE_TYPE", "USER_ID", "PAYMENT_STATUS"]',
       '["DROP", "DELETE", "UPDATE", "INSERT", "CREATE", "ALTER", "GRANT", "REVOKE", "TRUNCATE", "EXEC", "EXECUTE"]',
       1000,
       10000,
       '{
         "purpose": "Creator payment tracking and analysis",
         "key_relationships": "Payments linked to creators, campaigns, and companies via Stripe",
         "common_filters": ["payment_status", "payment_date", "creator_name", "campaign_name", "payment_amount"],
         "date_columns": ["created_date", "payment_date"],
         "amount_columns": ["payment_amount"],
         "text_columns": ["creator_name", "campaign_name", "payment_type", "company_name", "payment_status"],
         "id_columns": ["stripe_customer_id", "reference_id", "user_id"],
         "typical_queries": [
           "Recent payments to creators",
           "Pending payment analysis", 
           "Payment amounts by time period",
           "Creator payment summaries",
           "Campaign payment tracking"
         ]
       }'
   )
   ON CONFLICT (VIEW_NAME) DO UPDATE SET
       ALLOWED_OPERATIONS = EXCLUDED.ALLOWED_OPERATIONS,
       ALLOWED_COLUMNS = EXCLUDED.ALLOWED_COLUMNS,
       FORBIDDEN_KEYWORDS = EXCLUDED.FORBIDDEN_KEYWORDS,
       MAX_ROWS_DEFAULT = EXCLUDED.MAX_ROWS_DEFAULT,
       MAX_ROWS_LIMIT = EXCLUDED.MAX_ROWS_LIMIT,
       BUSINESS_CONTEXT = EXCLUDED.BUSINESS_CONTEXT,
       UPDATED_AT = CURRENT_TIMESTAMP();
   
   COMMIT;
   ```

3. Create `initialsetup/sql/03_setup_logging_tables.sql`:
   ```sql
   -- Setup and extend logging tables for MCP server usage
   -- Script: 03_setup_logging_tables.sql
   
   USE DATABASE PF;
   USE SCHEMA BI;
   
   -- Verify AI_USER_ACTIVITY_LOG exists and has required columns
   -- This table should already exist, but we'll document the expected schema
   
   /*
   Expected AI_USER_ACTIVITY_LOG structure:
   - ID (INTEGER) - Primary key
   - USER_ID (VARCHAR) - User identifier  
   - ACTIVITY_TYPE (VARCHAR) - Type of activity (mcp_tool_call, cortex_generation, etc.)
   - ACTIVITY_DETAILS (TEXT) - JSON details of the activity
   - NATURAL_QUERY (TEXT) - Original natural language query (for Cortex activities)
   - GENERATED_SQL (TEXT) - Generated SQL (for Cortex activities) 
   - EXECUTION_SUCCESS (BOOLEAN) - Whether operation succeeded
   - ROW_COUNT (INTEGER) - Number of rows returned/affected
   - EXECUTION_TIME_MS (INTEGER) - Execution time in milliseconds
   - CREATED_AT (TIMESTAMP_NTZ) - When activity occurred
   - METADATA (TEXT) - Additional JSON metadata
   */
   
   -- Add columns to AI_USER_ACTIVITY_LOG if they don't exist
   -- (Use ALTER TABLE IF COLUMN NOT EXISTS when available in your Snowflake version)
   
   -- For MCP server specific logging, you may want to add:
   ALTER TABLE AI_USER_ACTIVITY_LOG 
   ADD COLUMN IF NOT EXISTS MCP_TOOL_NAME VARCHAR(255);
   
   ALTER TABLE AI_USER_ACTIVITY_LOG 
   ADD COLUMN IF NOT EXISTS BEARER_TOKEN_HASH VARCHAR(255);
   
   ALTER TABLE AI_USER_ACTIVITY_LOG 
   ADD COLUMN IF NOT EXISTS REQUEST_ID VARCHAR(255);
   
   -- Create indexes for MCP server queries
   CREATE INDEX IF NOT EXISTS AI_USER_ACTIVITY_LOG_TOOL_IDX 
   ON AI_USER_ACTIVITY_LOG (MCP_TOOL_NAME);
   
   CREATE INDEX IF NOT EXISTS AI_USER_ACTIVITY_LOG_CREATED_IDX 
   ON AI_USER_ACTIVITY_LOG (CREATED_AT);
   
   CREATE INDEX IF NOT EXISTS AI_USER_ACTIVITY_LOG_SUCCESS_IDX 
   ON AI_USER_ACTIVITY_LOG (EXECUTION_SUCCESS);
   
   -- Verify AI_CORTEX_USAGE_LOG exists for Cortex credit tracking
   -- This table should track Cortex API usage and costs
   
   /*
   Expected AI_CORTEX_USAGE_LOG structure:
   - ID (INTEGER) - Primary key
   - REQUEST_ID (VARCHAR) - Unique request identifier
   - MODEL_NAME (VARCHAR) - Cortex model used
   - INPUT_TOKENS (INTEGER) - Tokens in prompt
   - OUTPUT_TOKENS (INTEGER) - Tokens in response
   - TOTAL_TOKENS (INTEGER) - Total tokens consumed
   - CREDITS_USED (FLOAT) - Cortex credits consumed
   - REQUEST_DURATION_MS (INTEGER) - Request duration
   - SUCCESS (BOOLEAN) - Whether request succeeded
   - ERROR_MESSAGE (TEXT) - Error details if failed
   - NATURAL_QUERY (TEXT) - Original natural language query
   - GENERATED_SQL (TEXT) - Generated SQL response
   - CREATED_AT (TIMESTAMP_NTZ) - When request occurred
   */
   
   COMMIT;
   
   -- Sample query to verify tables are set up correctly:
   -- SELECT COUNT(*) FROM AI_VIEW_CONSTRAINTS;
   -- SELECT COUNT(*) FROM AI_CORTEX_PROMPTS; 
   -- SELECT COUNT(*) FROM AI_USER_ACTIVITY_LOG;
   -- SELECT COUNT(*) FROM AI_CORTEX_USAGE_LOG;
   ```

4. Create `initialsetup/README.md`:
   ```markdown
   # Database Setup Scripts
   
   Run these SQL scripts in order to set up the required Snowflake tables for the MCP server:
   
   ## Prerequisites
   
   1. Connect to Snowflake with appropriate permissions to create tables and indexes
   2. Use database `PF` and schema `BI`
   3. Ensure you have CREATE TABLE and CREATE INDEX permissions
   
   ## Execution Order
   
   Execute scripts in numerical order:
   
   1. **01_create_ai_tables.sql** - Creates AI_VIEW_CONSTRAINTS and AI_CORTEX_PROMPTS tables
   2. **02_insert_view_constraints.sql** - Inserts security constraints for V_CREATOR_PAYMENTS_UNION
   3. **03_setup_logging_tables.sql** - Extends existing logging tables for MCP server usage
   
   ## Manual Execution
   
   ```sql
   -- Connect to Snowflake and run each script
   USE DATABASE PF;
   USE SCHEMA BI;
   
   -- Run 01_create_ai_tables.sql
   -- Run 02_insert_view_constraints.sql  
   -- Run 03_setup_logging_tables.sql
   ```
   
   ## Verification
   
   After running all scripts, verify tables are created:
   
   ```sql
   -- Check tables exist
   SHOW TABLES LIKE 'AI_%';
   
   -- Verify constraints are inserted
   SELECT * FROM AI_VIEW_CONSTRAINTS WHERE VIEW_NAME = 'V_CREATOR_PAYMENTS_UNION';
   
   -- Check logging table structure
   DESCRIBE TABLE AI_USER_ACTIVITY_LOG;
   ```
   
   ## Note
   
   Some tables (AI_USER_ACTIVITY_LOG, AI_CORTEX_USAGE_LOG, AI_SCHEMA_METADATA, AI_BUSINESS_CONTEXT) 
   may already exist in your environment. The scripts use `IF NOT EXISTS` clauses to avoid conflicts.
   ```

**Validation Gate:**
- All SQL scripts execute without errors
- Required tables are created with proper structure
- Constraints are inserted for V_CREATOR_PAYMENTS_UNION
- Logging tables are properly extended
- Verification queries return expected results

#### Task 5.2: Utility Functions and Response Helpers
**Input:** Common functionality requirements
**Output:** Reusable utility functions

**Implementation Steps:**
1. Implement `utils/response_helpers.py`:
   ```python
   import json
   from typing import Any, Dict
   from datetime import datetime
   
   def create_success_response(message: str, data: Any = None) -> Dict[str, Any]:
       """Create standardized success response for MCP tools"""
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
       """Create standardized error response for MCP tools"""
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

2. Implement `utils/logging.py`:
   ```python
   import json
   import logging
   import hashlib
   from typing import Dict, Any, Optional
   from datetime import datetime
   
   from auth.snowflake_auth import get_snowflake_connection
   from config.settings import settings
   
   async def log_activity(
       tool_name: str,
       arguments: Dict[str, Any],
       row_count: int = 0,
       execution_success: bool = True,
       execution_time_ms: Optional[int] = None,
       natural_query: Optional[str] = None,
       generated_sql: Optional[str] = None,
       bearer_token: Optional[str] = None
   ):
       """Log MCP tool activity to AI_USER_ACTIVITY_LOG"""
       try:
           conn = get_snowflake_connection(
               account=settings.snowflake_account,
               user=settings.snowflake_user,
               private_key_path=settings.snowflake_private_key_path,
               private_key_passphrase=settings.snowflake_private_key_passphrase,
               database=settings.snowflake_database,
               schema=settings.snowflake_schema,
               warehouse=settings.snowflake_warehouse
           )
           
           cursor = conn.cursor()
           
           # Hash bearer token for privacy
           bearer_token_hash = None
           if bearer_token:
               bearer_token_hash = hashlib.sha256(bearer_token.encode()).hexdigest()[:16]
           
           # Prepare activity details
           activity_details = json.dumps({
               "arguments": arguments,
               "execution_success": execution_success,
               "row_count": row_count,
               "execution_time_ms": execution_time_ms
           })
           
           insert_sql = """
           INSERT INTO AI_USER_ACTIVITY_LOG (
               USER_ID,
               ACTIVITY_TYPE,
               ACTIVITY_DETAILS,
               NATURAL_QUERY,
               GENERATED_SQL,
               EXECUTION_SUCCESS,
               ROW_COUNT,
               EXECUTION_TIME_MS,
               MCP_TOOL_NAME,
               BEARER_TOKEN_HASH,
               CREATED_AT
           ) VALUES (
               %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
           )
           """
           
           cursor.execute(insert_sql, (
               'mcp_user',  # Generic user ID for MCP server
               'mcp_tool_call',
               activity_details,
               natural_query,
               generated_sql,
               execution_success,
               row_count,
               execution_time_ms,
               tool_name,
               bearer_token_hash,
               datetime.now()
           ))
           
           cursor.close()
           conn.close()
           
       except Exception as error:
           # Don't fail the main operation if logging fails
           logging.warning(f"Failed to log activity: {error}")
   
   async def log_cortex_usage(
       natural_query: str,
       generated_sql: str,
       validation_passed: bool,
       view_name: str,
       model_name: str = None,
       credits_used: float = None,
       execution_time_ms: int = None
   ):
       """Log Cortex usage to AI_CORTEX_USAGE_LOG"""
       try:
           conn = get_snowflake_connection(
               account=settings.snowflake_account,
               user=settings.snowflake_user,
               private_key_path=settings.snowflake_private_key_path,
               private_key_passphrase=settings.snowflake_private_key_passphrase,
               database=settings.snowflake_database,
               schema=settings.snowflake_schema,
               warehouse=settings.snowflake_warehouse
           )
           
           cursor = conn.cursor()
           
           insert_sql = """
           INSERT INTO AI_CORTEX_USAGE_LOG (
               MODEL_NAME,
               NATURAL_QUERY,
               GENERATED_SQL,
               SUCCESS,
               CREDITS_USED,
               REQUEST_DURATION_MS,
               CREATED_AT
           ) VALUES (
               %s, %s, %s, %s, %s, %s, %s
           )
           """
           
           cursor.execute(insert_sql, (
               model_name or settings.cortex_model,
               natural_query,
               generated_sql,
               validation_passed,
               credits_used,
               execution_time_ms,
               datetime.now()
           ))
           
           cursor.close()
           conn.close()
           
       except Exception as error:
           logging.warning(f"Failed to log Cortex usage: {error}")
   
   def setup_logging():
       """Configure logging for the MCP server"""
       logging.basicConfig(
           level=logging.INFO,
           format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
           handlers=[
               logging.StreamHandler(),
               logging.FileHandler('mcp_server.log') if settings.environment == 'production' else logging.NullHandler()
           ]
       )
   ```

**Validation Gate:**
- Utility functions work correctly
- Response formatting is consistent across tools
- Activity logging successfully writes to Snowflake
- Cortex usage logging captures all required fields

### Phase 6: Testing and Validation

#### Task 6.1: Unit Tests for Core Components
**Input:** All implemented modules requiring testing
**Output:** Comprehensive test suite

**Implementation Steps:**
1. Implement `tests/test_auth.py`:
   ```python
   import pytest
   import os
   from unittest.mock import patch, MagicMock
   
   from auth.snowflake_auth import get_snowflake_connection
   from config.settings import settings
   
   class TestSnowflakeAuth:
       
       @patch('auth.snowflake_auth.snowflake.connector.connect')
       @patch('builtins.open')
       @patch('auth.snowflake_auth.load_pem_private_key')
       def test_successful_connection(self, mock_load_key, mock_open, mock_connect):
           """Test successful Snowflake connection with RSA key"""
           # Mock private key
           mock_key = MagicMock()
           mock_key.private_bytes.return_value = b'mock_der_bytes'
           mock_load_key.return_value = mock_key
           
           # Mock file operations
           mock_file = MagicMock()
           mock_file.read.return_value = b'mock_pem_data'
           mock_open.return_value.__enter__.return_value = mock_file
           
           # Mock connection
           mock_conn = MagicMock()
           mock_connect.return_value = mock_conn
           
           # Test connection
           result = get_snowflake_connection(
               account='test_account',
               user='test_user',
               private_key_path='test_path.pem',
               private_key_passphrase='test_pass'
           )
           
           # Assertions
           assert result == mock_conn
           mock_connect.assert_called_once()
           mock_load_key.assert_called_once()
       
       def test_missing_private_key_file(self):
           """Test error handling when private key file is missing"""
           with pytest.raises(FileNotFoundError):
               get_snowflake_connection(
                   account='test_account',
                   user='test_user',
                   private_key_path='nonexistent_key.pem'
               )
   ```

2. Implement `tests/test_sql_validation.py`:
   ```python
   import pytest
   
   from validators.sql_validator import SqlValidator
   
   class TestSqlValidator:
       
       def test_valid_select_query(self):
           """Test validation of valid SELECT query"""
           sql = "SELECT creator_name, payment_amount FROM V_CREATOR_PAYMENTS_UNION WHERE payment_status = 'PAID'"
           result = SqlValidator.validate_sql_query(sql)
           assert result.is_valid is True
       
       def test_dangerous_drop_query(self):
           """Test validation rejects DROP statements"""
           sql = "DROP TABLE V_CREATOR_PAYMENTS_UNION"
           result = SqlValidator.validate_sql_query(sql)
           assert result.is_valid is False
           assert "DROP" in result.error
       
       def test_dangerous_delete_query(self):
           """Test validation rejects DELETE statements"""
           sql = "DELETE FROM V_CREATOR_PAYMENTS_UNION WHERE payment_id = 1"
           result = SqlValidator.validate_sql_query(sql)
           assert result.is_valid is False
           assert "DELETE" in result.error
       
       def test_sql_injection_attempt(self):
           """Test validation rejects SQL injection patterns"""
           sql = "SELECT * FROM V_CREATOR_PAYMENTS_UNION WHERE creator_name = 'test' OR '1'='1'"
           result = SqlValidator.validate_sql_query(sql)
           assert result.is_valid is False
       
       def test_read_only_validation(self):
           """Test read-only query validation"""
           assert SqlValidator.is_read_only_query("SELECT * FROM table") is True
           assert SqlValidator.is_read_only_query("SHOW TABLES") is True
           assert SqlValidator.is_read_only_query("INSERT INTO table") is False
           assert SqlValidator.is_read_only_query("UPDATE table SET") is False
       
       def test_table_access_validation(self):
           """Test table access validation"""
           # Allowed table
           sql = "SELECT * FROM V_CREATOR_PAYMENTS_UNION"
           result = SqlValidator.validate_table_access(sql)
           assert result.is_valid is True
           
           # Disallowed table
           sql = "SELECT * FROM SENSITIVE_TABLE"
           result = SqlValidator.validate_table_access(sql)
           assert result.is_valid is False
   ```

3. Implement `tests/test_cortex_generation.py`:
   ```python
   import pytest
   from unittest.mock import patch, MagicMock, AsyncMock
   
   from cortex.cortex_generator import CortexGenerator, CortexRequest
   
   class TestCortexGenerator:
       
       @pytest.mark.asyncio
       @patch('cortex.cortex_generator.get_snowflake_connection')
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
   ```

4. Implement `tests/test_mcp_tools.py`:
   ```python
   import pytest
   from unittest.mock import patch, MagicMock, AsyncMock
   
   from tools.snowflake_tools import register_snowflake_tools
   from mcp.server import Server
   
   class TestMCPTools:
       
       def setup_method(self):
           """Setup test environment"""
           self.server = Server("Test Server")
           register_snowflake_tools(self.server)
       
       @pytest.mark.asyncio
       @patch('tools.snowflake_tools.get_snowflake_connection')
       async def test_list_databases_tool(self, mock_get_conn):
           """Test list_databases tool functionality"""
           # Mock database connection
           mock_conn = MagicMock()
           mock_cursor = MagicMock()
           mock_cursor.fetchall.return_value = [
               ('catalog', 'PF', 'database', None),
               ('catalog', 'STRIPE', 'database', None)
           ]
           mock_conn.cursor.return_value = mock_cursor
           mock_get_conn.return_value = mock_conn
           
           # Find the tool
           list_db_tool = None
           for tool in self.server.tools:
               if tool.name == "list_databases":
                   list_db_tool = tool
                   break
           
           assert list_db_tool is not None
           
           # Call tool
           result = await list_db_tool.handler({})
           
           # Assertions
           assert "content" in result
           assert len(result["content"]) > 0
           assert "Success" in result["content"][0]["text"]
       
       @pytest.mark.asyncio  
       @patch('tools.snowflake_tools.get_snowflake_connection')
       async def test_read_query_tool_with_validation(self, mock_get_conn):
           """Test read_query tool with SQL validation"""
           # Mock database connection
           mock_conn = MagicMock()
           mock_cursor = MagicMock()
           mock_cursor.fetchall.return_value = [('John Doe', 1000.0)]
           mock_cursor.description = [('CREATOR_NAME',), ('PAYMENT_AMOUNT',)]
           mock_conn.cursor.return_value = mock_cursor
           mock_get_conn.return_value = mock_conn
           
           # Find the tool
           read_query_tool = None
           for tool in self.server.tools:
               if tool.name == "read_query":
                   read_query_tool = tool
                   break
           
           assert read_query_tool is not None
           
           # Test valid query
           result = await read_query_tool.handler({
               "query": "SELECT creator_name, payment_amount FROM V_CREATOR_PAYMENTS_UNION"
           })
           
           assert "Success" in result["content"][0]["text"]
           
           # Test invalid query (should be rejected)
           result = await read_query_tool.handler({
               "query": "DROP TABLE V_CREATOR_PAYMENTS_UNION"
           })
           
           assert "Error" in result["content"][0]["text"]
           assert result["content"][0].get("isError") is True
   ```

**Validation Gate:**
- All unit tests pass
- Core authentication functionality is tested
- SQL validation is thoroughly tested
- Cortex generation is tested with mocks
- MCP tools are tested for both success and failure cases

#### Task 6.2: Integration Tests
**Input:** Complete MCP server implementation
**Output:** End-to-end integration tests

**Implementation Steps:**
1. Implement `tests/test_integration.py`:
   ```python
   import pytest
   import asyncio
   from unittest.mock import patch
   
   from server.mcp_server import SnowflakeMCP
   from config.settings import settings
   
   class TestMCPServerIntegration:
       
       @pytest.mark.asyncio
       async def test_server_initialization(self):
           """Test MCP server initializes successfully"""
           with patch('server.mcp_server.get_snowflake_connection') as mock_conn:
               # Mock successful connection test
               mock_conn.return_value.cursor.return_value.fetchone.return_value = (1,)
               
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
           with patch('server.mcp_server.get_snowflake_connection') as mock_conn:
               # Mock connection failure
               mock_conn.side_effect = Exception("Connection failed")
               
               server = SnowflakeMCP()
               
               # Should raise exception during init
               with pytest.raises(Exception):
                   await server.init()
       
       @pytest.mark.asyncio
       @patch('tools.snowflake_tools.get_snowflake_connection')
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
           server = SnowflakeMCP()
           await server.init()
           
           # Find read_query tool
           read_query_tool = None
           for tool in server.server.tools:
               if tool.name == "read_query":
                   read_query_tool = tool
                   break
           
           # Execute query
           result = await read_query_tool.handler({
               "query": "SELECT creator_name, payment_amount, payment_status FROM V_CREATOR_PAYMENTS_UNION WHERE payment_amount > 1000"
           })
           
           # Verify results
           assert "Success" in result["content"][0]["text"]
           assert "2 rows returned" in result["content"][0]["text"]
   ```

**Validation Gate:**
- Integration tests pass
- End-to-end functionality works correctly
- Error scenarios are handled gracefully
- All registered tools are accessible and functional

### Phase 7: Documentation and Deployment Preparation

#### Task 7.1: Environment Setup and Documentation
**Input:** Complete implementation requirements
**Output:** Production-ready configuration and documentation

**Implementation Steps:**
1. Create production `requirements.txt`:
   ```
   # Production requirements.txt
   mcp>=1.0.0
   fastapi>=0.104.0
   uvicorn[standard]>=0.24.0
   pydantic>=2.5.0
   snowflake-connector-python[pandas]>=3.5.0
   cryptography>=41.0.0
   google-cloud-secret-manager>=2.16.0
   python-dotenv>=1.0.0
   aiohttp>=3.8.0
   
   # Development and testing
   pytest>=7.4.0
   pytest-asyncio>=0.21.0
   black>=23.0.0
   ruff>=0.1.0
   mypy>=1.7.0
   ```

2. Create `pyproject.toml` for modern Python project configuration:
   ```toml
   [build-system]
   requires = ["hatchling"]
   build-backend = "hatchling.build"
   
   [project]
   name = "snowflake-mcp-server"
   version = "1.0.0"
   description = "Python-based MCP server for Snowflake integration with Open WebUI"
   authors = [{name = "Popfly", email = "dev@popfly.com"}]
   license = {text = "MIT"}
   readme = "README.md"
   requires-python = ">=3.9"
   dependencies = [
       "mcp>=1.0.0",
       "fastapi>=0.104.0",
       "uvicorn[standard]>=0.24.0",
       "pydantic>=2.5.0",
       "snowflake-connector-python[pandas]>=3.5.0",
       "cryptography>=41.0.0",
       "google-cloud-secret-manager>=2.16.0",
       "python-dotenv>=1.0.0",
       "aiohttp>=3.8.0",
   ]
   
   [project.optional-dependencies]
   dev = [
       "pytest>=7.4.0",
       "pytest-asyncio>=0.21.0",
       "black>=23.0.0",
       "ruff>=0.1.0",
       "mypy>=1.7.0",
   ]
   
   [project.scripts]
   mcp-server = "server.mcp_server:main"
   
   [tool.black]
   line-length = 100
   target-version = ['py39']
   
   [tool.ruff]
   line-length = 100
   target-version = "py39"
   select = ["E", "F", "W", "I", "N", "UP", "YTT", "S", "BLE", "B", "A", "COM", "C4", "DTZ", "T10", "EM", "EXE", "ISC", "ICN", "G", "INP", "PIE", "T20", "PYI", "PT", "Q", "RSE", "RET", "SLF", "SIM", "TID", "TCH", "ARG", "PTH", "PD", "PGH", "PL", "TRY", "NPY", "RUF"]
   ignore = ["E501", "S101", "PLR0913"]
   
   [tool.mypy]
   python_version = "3.9"
   strict = true
   warn_return_any = true
   warn_unused_configs = true
   disallow_untyped_defs = true
   ```

3. Create production `Dockerfile`:
   ```dockerfile
   # Multi-stage build for production deployment
   FROM python:3.11-slim AS base
   
   # Set environment variables
   ENV PYTHONUNBUFFERED=1 \
       PYTHONDONTWRITEBYTECODE=1 \
       PIP_NO_CACHE_DIR=1 \
       PIP_DISABLE_PIP_VERSION_CHECK=1
   
   # Create non-root user
   RUN groupadd -r appuser && useradd -r -g appuser appuser
   
   # Install system dependencies
   RUN apt-get update && apt-get install -y \
       gcc \
       && rm -rf /var/lib/apt/lists/*
   
   # Set working directory
   WORKDIR /app
   
   # Copy requirements and install Python dependencies
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   
   # Copy application code
   COPY . .
   
   # Change ownership to non-root user
   RUN chown -R appuser:appuser /app
   USER appuser
   
   # Health check
   HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
       CMD python -c "import sys; sys.exit(0)"
   
   # Run the MCP server
   CMD ["python", "-m", "server.mcp_server"]
   ```

4. Create `docker-compose.yml` for local development:
   ```yaml
   version: '3.8'
   
   services:
     mcp-server:
       build:
         context: .
         dockerfile: Dockerfile
       environment:
         - ENVIRONMENT=local
         - PYTHONPATH=/app
       env_file:
         - .env
       volumes:
         - ./auth:/app/auth:ro
         - ./logs:/app/logs
       ports:
         - "8000:8000"
       stdin_open: true
       tty: true
       restart: unless-stopped
   ```

**Validation Gate:**
- Production requirements are complete and tested
- Docker image builds successfully
- Docker compose setup works for local development
- Code quality tools (Black, Ruff, MyPy) pass

#### Task 7.2: CLI and Testing Tools
**Input:** Need for manual testing and debugging capabilities
**Output:** Command-line interface for testing MCP server

**Implementation Steps:**
1. Create `cli/mcp_cli.py`:
   ```python
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
           
           for tool in self.server.server.tools:
               print(f"🔧 {tool.name}")
               if hasattr(tool, 'description'):
                   print(f"   Description: {tool.description}")
               print()
       
       async def call_tool(self, tool_name: str, arguments: Dict[str, Any]):
           """Call a specific tool with arguments"""
           if not self.server:
               print("❌ Server not initialized")
               return
           
           # Find the tool
           target_tool = None
           for tool in self.server.server.tools:
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
               
               result = await target_tool.handler(arguments)
               
               print("📊 Result:")
               if isinstance(result, dict) and "content" in result:
                   for content in result["content"]:
                       if content.get("type") == "text":
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
   ```

2. Update `pyproject.toml` to include CLI script:
   ```toml
   [project.scripts]
   mcp-server = "server.mcp_server:main"
   mcp-cli = "cli.mcp_cli:main"
   ```

**Validation Gate:**
- CLI tool works for server initialization
- Tool listing functionality works
- Manual tool calling works with various argument types
- Error scenarios are handled gracefully

## Validation Loop

### Comprehensive Testing Protocol

**Phase 1: Unit Testing**
```bash
# Run all unit tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=. --cov-report=html

# Run specific test categories
python -m pytest tests/test_auth.py -v
python -m pytest tests/test_sql_validation.py -v
python -m pytest tests/test_cortex_generation.py -v
```

**Phase 2: Integration Testing**
```bash
# Test MCP server initialization
python -m cli.mcp_cli init

# Test tool availability
python -m cli.mcp_cli list

# Test basic Snowflake connectivity
python -m cli.mcp_cli call list_databases '{}'

# Test SQL validation
python -m cli.mcp_cli call read_query '{"query": "SELECT 1 as test"}'

# Test natural language query
python -m cli.mcp_cli call query_payments '{"query": "Show me recent payments"}'
```

**Phase 3: Security Validation**
```bash
# Test SQL injection prevention
python -m cli.mcp_cli call read_query '{"query": "SELECT * FROM V_CREATOR_PAYMENTS_UNION; DROP TABLE test;"}'

# Test dangerous operation prevention  
python -m cli.mcp_cli call read_query '{"query": "DELETE FROM V_CREATOR_PAYMENTS_UNION WHERE id = 1"}'

# Test table access restrictions
python -m cli.mcp_cli call read_query '{"query": "SELECT * FROM SENSITIVE_TABLE"}'
```

**Phase 4: Production Readiness**
```bash
# Code quality validation
black --check .
ruff check .
mypy .

# Build validation
docker build -t snowflake-mcp-server .

# Environment validation
python -c "from config.settings import settings; settings.validate_required_settings(); print('✅ Configuration valid')"
```

**Phase 5: MCP Protocol Testing**
```bash
# Test with MCP Inspector
npx @modelcontextprotocol/inspector@latest python -m server.mcp_server

# Manual Claude Desktop integration test
# (Requires updating claude_desktop_config.json)
```

### Success Criteria

**✅ All unit tests pass (100% core functionality)**
**✅ Integration tests pass (end-to-end workflow)**
**✅ Security validation prevents all dangerous operations**
**✅ MCP Inspector can connect and list tools**
**✅ Claude Desktop integration works**
**✅ Code quality tools pass (Black, Ruff, MyPy)**
**✅ Docker build succeeds**
**✅ Environment validation passes**
**✅ Database setup scripts execute without errors**
**✅ Cortex SQL generation works with natural language queries**

### Performance Benchmarks

**Query Response Time:** < 5 seconds for typical queries
**Cortex Generation Time:** < 10 seconds for complex natural language queries
**Tool Registration:** < 2 seconds for server initialization
**Memory Usage:** < 500MB under normal operation
**Database Connection Pool:** Efficient connection reuse

### Deployment Verification Checklist

**✅ All environment variables properly configured**
**✅ Snowflake connectivity works in target environment**
**✅ GCP Secret Manager integration (production only)**
**✅ Open WebUI bearer token authentication functional**
**✅ Database setup scripts executed successfully**
**✅ Logging and monitoring operational**
**✅ Health checks passing**
**✅ Error handling graceful under failure conditions**

## Expected Outcomes

### Primary Deliverables

1. **Fully Functional Python-based MCP Server** with Snowflake integration
2. **Six Direct Snowflake Tools** matching the existing MCP tool capabilities:
   - `list_databases` - Discover available databases  
   - `list_schemas` - Explore schema structure within databases
   - `list_tables` - Browse tables within specific schemas
   - `describe_table` - Get detailed table schema information
   - `read_query` - Execute read-only SQL queries safely
   - `append_insight` - Document insights from data analysis

3. **One Powerful Natural Language Tool**:
   - `query_payments` - Natural language queries for V_CREATOR_PAYMENTS_UNION using Cortex

4. **Production-Ready Authentication System**:
   - RSA private key authentication for Snowflake
   - Bearer token authentication for Open WebUI integration
   - Environment-aware configuration (local vs production)

5. **Comprehensive Security Framework**:
   - Multi-layered SQL injection protection
   - Table and column access whitelisting
   - Generated SQL validation before execution
   - Full audit trail of all queries and results

6. **Database Infrastructure**:
   - AI tables for Cortex constraints and prompt management
   - Enhanced logging for MCP tool usage tracking
   - View-specific security constraints configuration

### Technical Architecture Advantages

**Fewer, More Powerful Tools:**
- One `query_payments` tool handles 95% of payment analysis use cases
- Natural language interface reduces cognitive load on LLM
- Cortex provides flexibility without code changes for new query patterns

**Security Through Multiple Layers:**
- Open WebUI bearer token authentication (first layer)
- SQL pattern validation (second layer)  
- Table access whitelisting (third layer)
- Generated SQL validation (fourth layer)
- Comprehensive audit logging (monitoring layer)

**Flexible Deployment:**
- Local development with `.env` files
- Production deployment on GCP with Secret Manager
- Docker containerization for consistent environments
- Environment-specific configuration management

**Natural Language Integration:**
- Snowflake Cortex COMPLETE function for SQL generation
- Business context injection for better query generation
- Prompt optimization based on usage patterns
- Transparent operation (user can see generated SQL)

### Integration Benefits

**For Open WebUI Users:**
- Natural language interface for data analysis
- No need to learn SQL or tool-specific parameters
- Transparent operation with generated SQL visibility
- Consistent error handling and helpful feedback

**For Developers:**
- Minimal maintenance overhead (one tool handles many use cases)
- Easy to extend with new views by following established patterns
- Centralized business logic in Cortex prompts
- Standard Python patterns with full type safety

**For Operations:**
- Complete audit trail from natural language → SQL → results
- Usage tracking and cost monitoring for Cortex
- Security validation at multiple levels
- Graceful error handling and logging

**For Business Users:**
- Ask questions about creator payments in natural language
- Get consistent, validated results from trusted data source
- Self-service analytics capability
- Reduced dependency on technical team for basic queries

This implementation provides the foundation for a scalable, secure, and user-friendly data access platform that bridges the gap between natural language queries and structured data analysis while maintaining enterprise-grade security and operational oversight.