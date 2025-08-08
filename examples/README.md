# Snowflake MCP Server Examples

This directory contains example implementations for building a Snowflake MCP server with Open WebUI integration. All examples demonstrate reliable connection patterns and best practices.

## Directory Structure

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

### Reference Implementations
- `sflake/` - Reference implementations from existing project
  - `popfly_prod_to_snowflake.py` - Data replication script
  - `replicate_stripe_views.py` - View replication script

- `identity_resolution/utils/` - Advanced connection management
  - `snowflake_connector.py` - Class-based connection management

### Database Setup
- `sql/initialsetup/` - Database initialization scripts
  - `01_create_ai_tables.sql` - Create AI_VIEW_CONSTRAINTS and AI_CORTEX_PROMPTS tables
  - `02_insert_view_constraints.sql` - Insert security constraints for views
  - `03_setup_logging_tables.sql` - Documentation for logging table usage

### Configuration
- `config/` - Configuration templates
  - `.env.example` - Environment variables template
  - `requirements.txt` - Python dependencies

## Usage

These examples demonstrate:

1. **Reliable Snowflake Connections**: RSA key authentication with proper error handling
2. **Environment Management**: Local development vs production deployment
3. **Open WebUI Integration**: Bearer token authentication
4. **Cortex SQL Generation**: Natural language to SQL conversion
5. **Security Validation**: SQL validation to prevent malicious queries
6. **Tool Architecture**: Natural language tools vs traditional specific tools

## Key Patterns

- **Centralized Authentication**: All scripts import from auth modules
- **Environment Switching**: Seamless local/production configuration
- **Error Handling**: Consistent try/catch patterns with meaningful messages
- **Resource Management**: Proper connection and cursor cleanup
- **Security First**: Multiple layers of validation and constraints

## Implementation Order

1. Start with `auth/snowflake_auth.py` for basic connection
2. Add `config/environment_config.py` for environment management
3. Implement `auth_middleware/bearer_auth.py` for Open WebUI auth
4. Build `server/mcp_server.py` as the main server
5. Create `tools/natural_language_tool.py` for natural language queries
6. Add `cortex/cortex_generator.py` for SQL generation
7. Implement `validators/sql_validator.py` for security
8. Run `sql/initialsetup/` scripts to set up database tables
9. Configure `config/.env.example` for your environment
10. Reference `sflake/` examples for production patterns

## Notes

- All examples are standalone and can be used as templates
- The `sflake/` directory contains actual production code from the transformations project
- Examples include proper imports and dependencies
- Security patterns are demonstrated throughout
- Error handling and logging are included in all examples
