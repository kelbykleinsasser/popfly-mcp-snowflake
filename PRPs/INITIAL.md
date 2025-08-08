## FEATURE:

We want to create a Python-based MCP (Model Context Protocol) server that integrates with Open WebUI as a tool, leveraging Snowflake Cortex's SQL generation capabilities for natural language querying with security constraints. Also provide a simple CLI within the project to call and test the MCP server manually.

**IMPORTANT**: This project builds an MCP server that Open WebUI will access as a tool. We are NOT building or modifying Open WebUI itself - Open WebUI is already deployed and configured separately.

### Integration with Open WebUI:

- **Open WebUI Role**: Provides the UI and tool management interface (out of scope for this project)
- **MCP Server Role**: Implements tools that Open WebUI can register and call
- **Authentication**: MCP server must support Open WebUI's bearer token authentication
- **Registration**: Admin registers MCP server URL in Open WebUI's tool management UI

### Deployment Architecture:

- **Local Development**: Run MCP server locally with `.env` file for secrets
- **Production (GCP)**: Deploy as containerized service using GCP Secret Manager
- **Environment Toggle**: Use `ENVIRONMENT` variable to switch between `local` and `production`

Key architecture principles:

- **Static tool registration**: Tools are defined in MCP server and registered via Open WebUI's built-in UI
- **Dynamic query behavior**: Each tool uses Cortex to handle varied natural language queries
- **Bearer token auth**: Support Open WebUI's native authentication system
- **Fewer, more powerful tools**: One flexible natural language tool instead of dozens of specific ones
- **Cortex-powered SQL generation**: Use Snowflake Cortex COMPLETE function to generate SQL from natural language queries
- **Constrained generation**: Cortex generates SQL only for whitelisted views with validated operations
- **Security through validation**: Post-generation SQL validation ensures only safe queries execute
- **RSA key-pair authentication**: Use SVC_POPFLY_APP service account with private key authentication for Snowflake (no MFA)
- **Comprehensive logging**: Track all queries (template-based and Cortex-generated) in AI_USER_ACTIVITY_LOG
- **Transparency**: Always show generated SQL to users for verification

### Static Tools with Dynamic Behavior:

**Traditional Approach (Many Static Tools)**:
- `search_payments_by_creator`
- `search_payments_by_date_range`
- `search_payments_by_amount`
- `filter_payments_by_status`
- `find_pending_payments_over_amount`
- ... dozens more for every combination

**Our Approach (Few Powerful Tools)**:
- `query_payments` - Handles ALL payment queries via natural language

This reduces cognitive load on the LLM and provides a more natural user experience.

We need:

- **MCP server with Open WebUI authentication support** (bearer tokens)
- **Environment configuration** for local development and GCP production
- **GCP Secret Manager integration** for production secrets
- **One primary natural language tool** per view (not dozens of specific tools)
- Cortex integration module for SQL generation using COMPLETE function
- SQL validation layer to ensure generated queries are safe
- Constraint definitions for each view (allowed operations, columns, joins)
- Activity logging with natural language query, generated SQL, and execution metrics
- Query timeout enforcement (30 seconds default)
- Result limiting (1000 rows default, 10000 max)

### Tool Registration Flow with Open WebUI:

1. Deploy MCP server (local or GCP)
2. MCP server exposes endpoints with bearer token authentication
3. Admin generates API key in Open WebUI (Settings > Account)
4. Admin registers MCP server URL with API key in Open WebUI's tool management UI
5. Open WebUI calls MCP server's `list_tools()` to discover available tools
6. Admin selects/enables tools in Open WebUI's interface
7. Tools are now available to all users (static registration complete)
8. Each tool can handle diverse queries dynamically via Cortex

## EXAMPLES:

The following files demonstrate the reliable Snowflake connection patterns used in this project. These examples show how to implement RSA private key authentication, handle environment configuration, and integrate with Google Secret Manager for production deployments. The examples are not meant to be follow verbatim, but warn the user if a contradiction is discovered or if a significant departure from the examples provided is warranted.

### Core Authentication Files:

**`examples/auth/snowflake_auth.py`** - Primary authentication module that demonstrates:
- RSA private key loading from file
- Key format conversion (PEM to DER) for Snowflake compatibility
- Connection establishment with all required parameters
- Environment variable configuration using dotenv
- Centralized connection function used by all other modules

**`examples/auth/snowflake_auth_secure.py`** - Production-ready authentication using Google Secret Manager:
- Temporary file handling for private keys from GCP secrets
- Secret Manager integration with fallback to local environment
- Proper cleanup of temporary files to prevent credential exposure
- Error handling and logging for production environments

**`examples/auth/secret_manager.py`** - Centralized secret management system:
- Google Secret Manager client with local environment fallback
- Configuration structure for Snowflake connection parameters
- Error handling and logging for secret access
- Support for both local development and production environments

### Usage Pattern Examples:

**`examples/sflake/popfly_prod_to_snowflake.py`** - Data replication script showing:
- How to import and use the centralized auth module
- Connection establishment pattern with error handling
- Database and schema switching after connection
- Integration with existing authentication infrastructure

**`examples/sflake/replicate_stripe_views.py`** - View replication script demonstrating:
- Simple connection wrapper pattern
- Consistent error handling across different operations
- Integration with the centralized auth module
- Production-ready connection management

**`examples/identity_resolution/utils/snowflake_connector.py`** - Class-based connection management:
- Object-oriented approach to Snowflake connections
- Import pattern for the auth module
- Connection reuse across multiple operations
- Advanced data processing with pandas integration

### Open WebUI Authentication Handler:

See `examples/auth_middleware/bearer_auth.py` for the complete authentication implementation. This is **critical for security** as it validates bearer tokens from Open WebUI, ensuring only authorized users can access the MCP server. The implementation includes proper error handling and supports both local development and production environments.

### Environment Configuration:

See `examples/config/environment_config.py` for the complete environment configuration implementation. This enables **seamless deployment** by automatically switching between local development (using .env files) and production (using GCP Secret Manager), ensuring secure credential management across environments.

### MCP Server with Open WebUI Auth:

See `examples/server/mcp_server.py` for the complete MCP server implementation with authentication. This demonstrates the **core MCP protocol integration** with Open WebUI, including tool registration, request handling, and proper authentication flow. The server acts as the bridge between Open WebUI's interface and Snowflake's data.

### Cortex SQL Generation Example:

See `examples/cortex/sql_generator.py` for the complete Cortex SQL generation implementation. This shows the **fundamental Cortex integration** that converts natural language queries into SQL, demonstrating proper prompt engineering and error handling for the COMPLETE function.

### SQL Validation Pattern:

See `examples/validators/sql_validator.py` for the complete SQL validation implementation. This provides **critical security validation** by checking generated SQL against whitelisted operations and columns, preventing malicious queries and ensuring data access controls are enforced.

### Comparison Example - Traditional MCP vs Our Approach:

See `examples/tools/comparison_examples.py` for the complete comparison between traditional and our approach. This demonstrates the **architectural advantage** of using natural language tools with Cortex over traditional specific tools, showing how this reduces cognitive load on the LLM and provides a more intuitive user experience.

## DOCUMENTATION:

### Open WebUI Integration:
- Open WebUI API Authentication: https://docs.openwebui.com/getting-started/api-endpoints/ - Shows bearer token authentication using API keys from Settings > Account
- Open WebUI Monitoring Guide: https://docs.openwebui.com/getting-started/advanced-topics/monitoring/ - Details on API key setup and authentication headers
- Open WebUI API Discussion: https://github.com/open-webui/open-webui/discussions/1349 - Examples of API token usage

### MCP Protocol:
- MCP SDK Documentation: https://modelcontextprotocol.io/docs/python
- MCP Server Examples: https://github.com/modelcontextprotocol/servers

### Snowflake Cortex:
- Snowflake Cortex COMPLETE: https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions#complete

### GCP Deployment:
- GCP Secret Manager Python Client: https://cloud.google.com/secret-manager/docs/creating-and-accessing-secrets#python
- Cloud Run Deployment: https://cloud.google.com/run/docs/deploying

## OTHER CONSIDERATIONS:

### Open WebUI is Out of Scope:

- **We are NOT modifying Open WebUI** - it's already deployed and configured
- **We are NOT implementing Open WebUI features** - just building an MCP server it can use
- **We ARE implementing bearer token auth** - to integrate with Open WebUI's existing auth system
- **We ARE following MCP protocol** - so Open WebUI can register and use our tools

### Authentication Implementation:

Open WebUI uses bearer token authentication for external tools:
- Users generate API keys in Settings > Account within Open WebUI
- All API requests require Authorization header: "Bearer YOUR_API_KEY"
- MCP server must validate bearer tokens on all endpoints
- Store expected tokens securely (local: .env, production: GCP Secret Manager)

### Environment Management:

**Local Development**:
- Use `.env` file for all secrets
- Set `ENVIRONMENT=local`
- Store Snowflake private key as file
- Use plain text API keys for testing

**Production (GCP)**:
- Use GCP Secret Manager for all secrets
- Set `ENVIRONMENT=production` 
- Store Snowflake private key as secret (not file)
- During deployment, open connection between current Open WebIU container and the MCP server
- Rotate API keys regularly

**Configuration Toggle**:
```python
# .env.local
ENVIRONMENT=local
SNOWFLAKE_PRIVATE_KEY_PATH=auth/snowflake_key.pem
OPEN_WEBUI_API_KEY=test-key-12345

# .env.production (or set in GCP)
ENVIRONMENT=production
GCP_PROJECT_ID=your-project-id
# All other secrets in GCP Secret Manager
```

### Design Principle: Fewer, More Powerful Tools

Instead of creating dozens of specific tools, we create one primary tool per view that leverages Cortex for flexibility.

### Primary Tool for V_CREATOR_PAYMENTS_UNION:

```python
{
    "tool_name": "query_payments",
    "description": "Query creator payments using natural language. Handles all payment-related questions including filtering by creator, date, amount, status, campaign, and more.",
    "parameters": {
        "query": {
            "type": "string", 
            "description": "Natural language query about creator payments",
            "examples": [
                "Show me all payments to creators in the last 30 days",
                "Find payments over $1000 that are still pending",
                "Which creators received payments for campaign X in January?",
                "Total payments by month for creator John Smith",
                "List failed payments with amounts over $500"
            ]
        },
        "include_sql": {
            "type": "boolean",
            "description": "Include the generated SQL in the response",
            "default": true
        },
        "max_rows": {
            "type": "integer",
            "description": "Maximum number of rows to return",
            "default": 1000,
            "maximum": 10000
        }
    },
    "cortex_config": {
        "model": "llama3.1-70b",  # or later model
        "view_name": "V_CREATOR_PAYMENTS_UNION",
        "allowed_operations": ["SELECT", "WHERE", "GROUP BY", "ORDER BY", "LIMIT"],
        "timeout": 10
    }
}
```


### Why This Approach Works:

- **One tool to rule them all**: `query_payments` handles 95% of use cases
- **Natural language is the interface**: Users don't need to understand tool parameters
- **Cortex provides flexibility**: New query patterns work without code changes
- **LLM has less cognitive load**: Choosing between 2-3 tools vs 20-30 tools

### V_CREATOR_PAYMENTS_UNION columns (verified from Snowflake):
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

### Required AI tables:

All SQL scripts for database setup must be stored in the `examples/sql/initialsetup/` directory as separate .sql files. These scripts should be numbered sequentially (e.g., 01_create_tables.sql, 02_insert_data.sql) to ensure proper execution order.  The examples are not meant to be follow verbatim, but warn the user if a contradiction is discovered or if a significant departure from the examples provided is warranted. It's also fine if you believe that a database change structure change is warranted. If necessary, use your existing MCP Snowflake connection to examine the database schema or data.

**AI_VIEW_CONSTRAINTS** - Security constraints for Cortex SQL generation:
See `examples/sql/initialsetup/01_create_ai_tables.sql` for the complete table creation script. This table is **critical for security** as it defines what operations and columns are allowed for each view, preventing malicious SQL generation by Cortex.

**AI_CORTEX_PROMPTS** - Optimized prompts for better SQL generation:
See `examples/sql/initialsetup/01_create_ai_tables.sql` for the complete table creation script. This table enables **prompt optimization** by tracking which prompts work best for different query types, allowing continuous improvement of SQL generation quality.

**View Constraints Setup**:
See `examples/sql/initialsetup/02_insert_view_constraints.sql` for the complete constraints insertion script. This defines the **security boundaries** for the V_CREATOR_PAYMENTS_UNION view, including allowed operations, forbidden keywords, and column descriptions that help Cortex understand the data.

### Existing AI tables to leverage:

**AI_USER_ACTIVITY_LOG** (Already exists) - Enhanced for Cortex tracking:
See `examples/sql/initialsetup/03_setup_logging_tables.sql` for the complete logging setup documentation. This table provides **comprehensive audit trails** by logging natural language queries, generated SQL, validation results, and execution metrics - essential for security, debugging, and usage analytics.

**AI_CORTEX_USAGE_LOG** (Already exists) - Track Cortex credit usage:
- Log every COMPLETE function call
- Monitor token usage and costs
- Track success/failure rates
- Analyze query patterns for optimization

**AI_SCHEMA_METADATA** (Already exists) - Enhance Cortex understanding:
- Document each column with business meaning
- Provide example values for better SQL generation
- Include relationships between columns
- Store common query patterns per column

**AI_BUSINESS_CONTEXT** (Already exists) - Guide Cortex generation:
- Business rules that affect query logic
- Common analysis patterns
- Domain-specific terminology
- Query interpretation guidelines
- Can help LLM understand which tool to use for specific business questions

### Required Project Structure:

**Note**: The `examples/` directory contains reference implementations from the existing transformations project that demonstrate the reliable Snowflake connection patterns. Use these as templates for the MCP server implementation.

## Examples Directory Structure

The `examples/` directory provides a complete reference implementation with the following structure:

### Authentication & Configuration
- `auth/` - Snowflake authentication examples
  - `snowflake_auth.py` - Basic RSA key authentication
  - `snowflake_auth_secure.py` - Production-ready with Secret Manager
  - `secret_manager.py` - Centralized secret management
  - `snowflake_auth_mcp.py` - MCP-specific authentication implementation

- `auth_middleware/` - Open WebUI authentication
  - `bearer_auth.py` - Bearer token validation for Open WebUI

- `config/` - Environment configuration
  - `environment_config.py` - Environment switching between local and production
  - `.env.example` - Environment variables template
  - `requirements.txt` - Python dependencies

### Server & Tools
- `server/` - MCP server implementation
  - `mcp_server.py` - Main MCP server with authentication handlers

- `tools/` - Tool implementations
  - `natural_language_tool.py` - Natural language query tool using Cortex
  - `comparison_examples.py` - Traditional vs our approach comparison

### Cortex Integration
- `cortex/` - Snowflake Cortex integration
  - `sql_generator.py` - Basic Cortex SQL generation
  - `cortex_generator.py` - Complete Cortex SQL generation module

### Validation & Security
- `validators/` - SQL validation
  - `sql_validator.py` - SQL validation for security

### Database Setup
- `sql/initialsetup/` - Database initialization scripts
  - `01_create_ai_tables.sql` - Create AI_VIEW_CONSTRAINTS and AI_CORTEX_PROMPTS tables
  - `02_insert_view_constraints.sql` - Insert security constraints for views
  - `03_setup_logging_tables.sql` - Documentation for logging table usage

### Reference Implementations
- `sflake/` - Reference implementations from existing project
  - `popfly_prod_to_snowflake.py` - Data replication script
  - `replicate_stripe_views.py` - View replication script

- `identity_resolution/utils/` - Advanced connection management
  - `snowflake_connector.py` - Class-based connection management

## Implementation Order

Follow this sequence for building the MCP server:

1. Start with `auth/snowflake_auth.py` for basic connection
2. Add `config/environment_config.py` for environment management
3. Implement `auth_middleware/bearer_auth.py` for Open WebUI auth
4. Build `server/mcp_server.py` as the main server
5. Create `tools/natural_language_tool.py` for natural language queries
6. Add `cortex/cortex_generator.py` for SQL generation
7. Implement `validators/sql_validator.py` for security
8. Run `sql/initialsetup/` scripts to set up database tables or verify that they exist and write initial data
9. Configure `config/.env.example` for your environment
10. Reference `sflake/` examples for production patterns

## Key Patterns Demonstrated

- **Centralized Authentication**: All scripts import from auth modules
- **Environment Switching**: Seamless local/production configuration
- **Error Handling**: Consistent try/catch patterns with meaningful messages
- **Resource Management**: Proper connection and cursor cleanup
- **Security First**: Multiple layers of validation and constraints

## What the Examples Demonstrate

These examples provide comprehensive coverage of:

1. **Reliable Snowflake Connections**: RSA key authentication with proper error handling
2. **Environment Management**: Local development vs production deployment
3. **Open WebUI Integration**: Bearer token authentication
4. **Cortex SQL Generation**: Natural language to SQL conversion
5. **Security Validation**: SQL validation to prevent malicious queries
6. **Tool Architecture**: Natural language tools vs traditional specific tools

```
snowflake-mcp/
├── auth/
│   ├── __init__.py
│   ├── snowflake_auth.py          # COPY EXACTLY from examples/auth/snowflake_auth.py
│   └── snowflake_key.pem          # Private key file (DO NOT COMMIT)
├── server/
│   ├── __init__.py
│   ├── mcp_server.py              # Main MCP server with auth handlers
│   └── handlers.py                # Request handlers
├── cortex/
│   ├── __init__.py
│   ├── sql_generator.py           # Cortex COMPLETE integration
│   ├── sql_validator.py           # Validate generated SQL
│   ├── prompt_manager.py          # Manage Cortex prompts
│   └── constraints.py             # View-specific constraints
├── tools/
│   ├── __init__.py
│   ├── base_tool.py               # Base class for all tools
│   └── natural_language_tool.py   # THE primary tool using Cortex
├── validators/
│   ├── __init__.py
│   ├── sql_parser.py              # Parse and validate SQL
│   └── parameter_validator.py     # Input parameter validation
├── auth_middleware/
│   ├── __init__.py
│   └── bearer_auth.py             # Open WebUI bearer token validation
├── utils/
│   ├── __init__.py
│   ├── logging.py                 # Activity logging to Snowflake
│   ├── cache.py                   # Cache Cortex-generated SQL
│   └── config.py                  # Environment configuration
├── config/
│   ├── __init__.py
│   └── settings.py                # Environment settings
├── initialsetup/
│   └── sql/
│       ├── 01_create_ai_tables.sql        # Create AI_VIEW_CONSTRAINTS, AI_CORTEX_PROMPTS
│       ├── 02_insert_view_constraints.sql  # Insert constraints for views
│       ├── 03_setup_logging_tables.sql     # Extend AI_USER_ACTIVITY_LOG if needed
│       └── README.md                       # Instructions for running setup scripts
├── tests/
│   ├── __init__.py
│   ├── test_auth.py               # Test bearer token validation
│   ├── test_cortex_generation.py  # Test SQL generation
│   ├── test_sql_validation.py     # Test security validation
│   └── test_integration.py        # End-to-end tests
├── deployment/
│   ├── Dockerfile                 # Multi-stage build
│   ├── cloudbuild.yaml           # GCP Cloud Build config
│   └── k8s/                      # Kubernetes manifests
├── .env.example                   # Local dev template
├── .gitignore                     # Must include auth/*.pem
├── requirements.txt
├── README.md
└── docker-compose.yml             # Local testing
```

### Required Environment Variables:

See `examples/config/.env.example` for the complete environment configuration template. This file demonstrates **environment switching** between local development and production deployment, with all necessary variables for Snowflake connection, Open WebUI integration, Cortex configuration, and security settings.

### Required Dependencies:

See `examples/config/requirements.txt` for the complete dependency list. This includes all necessary packages for **Snowflake connectivity**, **MCP server implementation**, **Cortex integration**, **security validation**, and **production deployment**.

### Snowflake Auth Module:

See `examples/auth/snowflake_auth_mcp.py` for the complete Snowflake authentication implementation. This provides **reliable RSA key authentication** with proper key format conversion and environment-aware configuration, ensuring secure and stable connections to Snowflake across all deployment scenarios.

### Cortex SQL Generation Module:

See `examples/cortex/cortex_generator.py` for the complete Cortex SQL generation implementation. This provides **comprehensive Cortex integration** with advanced prompt engineering, proper error handling, and logging capabilities. The module demonstrates how to build robust natural language to SQL conversion with business context and security constraints.

### Natural Language Tool Pattern:

See `examples/tools/natural_language_tool.py` for the complete natural language tool implementation. This demonstrates the **core tool architecture** that combines Cortex SQL generation, validation, caching, and execution into a single powerful interface. The pattern shows how to create flexible tools that handle diverse queries while maintaining security and performance.

### Security Model:

Even with natural language flexibility, security is maintained through multiple layers:

- **Open WebUI Auth**: Bearer token required for all MCP endpoints
- **Pre-generation constraints**: Cortex prompts explicitly state security requirements
- **Post-generation validation**: SQL parser ensures no forbidden operations
- **View isolation**: Each tool only accesses its designated view
- **Column whitelisting**: Only approved columns can be queried
- **Result limits**: Automatic row count limits prevent data exfiltration
- **Full audit trail**: Every query logged with user, input, generated SQL, and results

### When to Use Cortex (Primary Approach):

Since we're optimizing for fewer, more powerful tools, Cortex is the default for handling queries:

**Always Use Cortex for**:
- All natural language queries through the primary tool
- Any query that doesn't exactly match a pre-built report format
- Exploratory questions where users don't know exact parameters
- Complex filtering with multiple conditions

**Only Create Separate Tools When**:
- You need a specific output format (e.g., Excel report generation)
- There's a complex multi-step process that Cortex can't handle in one query
- Business logic requires specific calculations beyond SQL
- Performance requirements demand a highly optimized stored procedure

### Cortex Implementation Best Practices:

**Prompt Engineering**:
- Include clear constraints in every prompt
- Provide column descriptions and example values
- Specify exact output format requirements
- Include business rules that affect queries

**Model Selection**:
- Use `llama3.1-70b` or later models for best SQL generation
- Monitor new model releases for improvements
- Test prompts when upgrading models

**Caching Strategy**:
- Cache identical natural language queries for 5 minutes
- Cache SQL generation separate from execution
- Log cache hit rates to optimize

**Error Handling**:
- If Cortex fails, return helpful error to user
- Log failures for prompt optimization
- Consider fallback to basic SELECT * with filters

### GCP Deployment Considerations:

**Database Initialization**:
- Run all SQL scripts in `initialsetup/sql/` directory in sequence
- Scripts are numbered to ensure proper execution order
- Can be automated in deployment pipeline or run manually
- Verify all tables created successfully before starting MCP server

**Container Structure**:
- Use multi-stage Docker build for smaller images
- Include only production dependencies
- Run as non-root user

**Secret Management**:
- Never include secrets in container image
- Use GCP Secret Manager for all sensitive data
- Grant minimal IAM permissions

**Health Checks**:
- Implement `/health` endpoint for GCP load balancer
- Check both MCP server and Snowflake connectivity
- Return appropriate HTTP status codes

**Scaling**:
- MCP server should be stateless
- Use Cloud Run for automatic scaling
- Consider connection pooling for Snowflake

### Database Setup Scripts:

All SQL scripts must be stored in `initialsetup/sql/` directory with sequential numbering:

```
initialsetup/sql/
├── 01_create_ai_tables.sql        # Create AI_VIEW_CONSTRAINTS, AI_CORTEX_PROMPTS
├── 02_insert_view_constraints.sql  # Insert constraints for V_CREATOR_PAYMENTS_UNION
├── 03_setup_logging_tables.sql     # Extend AI_USER_ACTIVITY_LOG if needed
├── 04_insert_sample_prompts.sql    # Optional: Insert sample Cortex prompts
└── README.md                       # Instructions for running setup scripts
```

Example README.md content:
```markdown
# Database Setup Scripts

Run these scripts in order to set up the required Snowflake tables:

1. Connect to Snowflake with appropriate permissions
2. Use database PF and schema BI
3. Execute scripts in numerical order:
   - 01_create_ai_tables.sql - Creates new AI tables
   - 02_insert_view_constraints.sql - Sets up view constraints
   - 03_setup_logging_tables.sql - Extends existing logging tables
   - 04_insert_sample_prompts.sql - (Optional) Sample Cortex prompts

Note: Some tables may already exist. Scripts use IF NOT EXISTS clauses.
```

### Testing Requirements:

**Local Testing**:
- Test with mock Open WebUI bearer tokens
- Verify Cortex SQL generation with various queries
- Test SQL validation catches forbidden operations
- Verify environment switching works correctly

**Integration Testing**:
- Test actual Open WebUI integration with local MCP server
- Verify bearer token validation
- Test tool discovery and execution flow
- Validate error handling and logging

### Common Pitfalls to Avoid:

- **Don't expose Snowflake credentials** - Use proper secret management
- **Don't skip bearer token validation** - Security is critical
- **Don't hardcode environment configs** - Use environment variables
- **Don't trust Cortex blindly** - Always validate generated SQL
- **Don't forget to handle Cortex failures** - Have fallback behavior
- **Don't mix test and prod configs** - Clear environment separation
- **Don't store secrets in code** - Use .env locally, GCP Secrets in prod
- **Don't assume Open WebUI structure** - We're just building the MCP server
- **Don't implement Open WebUI features** - Stay focused on MCP protocol
- **Don't embed SQL in code** - All database setup SQL must be in initialsetup/sql/ directory
- **Don't forget SQL script ordering** - Number scripts sequentially (01_, 02_, etc.)

### Future Extensibility:

- **Adding new views**: Create one natural language tool per view
- **Improving Cortex prompts**: Update prompts based on usage patterns
- **Adding business logic**: Enhance prompts with domain-specific rules
- **Performance optimization**: Cache frequently used queries
- **Multi-view queries**: Future enhancement to support JOIN operations with validation

### Benefits of This Architecture:

**For Users**:
- Natural language interface - no need to understand SQL or tool parameters
- Flexible queries - ask anything about the data
- Transparent - can see the generated SQL

**For Developers**:
- Minimal code - one tool implementation handles all query types
- Easy to extend - add new views by creating similar tools
- Centralized logic - all SQL generation in one place

**For Operations**:
- Fewer tools to manage and document
- Consistent behavior across all queries
- Clear audit trail of natural language → SQL → results
- Easy deployment with Docker and GCP

## ARCHITECTURAL SUMMARY:

**MCP Server for Open WebUI**:
- We build the MCP server, not Open WebUI
- Integrates via bearer token authentication
- Follows standard MCP protocol

**Static Registration + Dynamic Behavior**:
- Tools are registered once in Open WebUI's UI (static)
- Each tool uses Cortex to handle diverse queries (dynamic)
- Best of both worlds: simple setup, powerful functionality

**Fewer Tools, More Power**:
- One `query_payments` tool replaces dozens of specific query tools
- Natural language is the universal interface
- LLM has less cognitive load, users have better experience

**Security Through Validation**:
- Open WebUI bearer token authentication required
- Cortex generates SQL with constraints
- Every query is validated before execution
- Full audit trail and transparency

**Flexible Deployment**:
- Local development with .env files
- Production deployment on GCP with Secret Manager
- Easy switching between environments

This architecture leverages Cortex's power while integrating seamlessly with Open WebUI's standard tool authentication and registration process.