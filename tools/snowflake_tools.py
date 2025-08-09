import json
import logging
import time
from typing import Dict, Any, List
from mcp.types import Tool, TextContent
from pydantic import BaseModel, validator

from utils.config import get_environment_snowflake_connection
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
    def validate_strings(cls, v):
        if not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip().upper()

class DescribeTableSchema(BaseModel):
    table_name: str
    
    @validator('table_name')
    def validate_table_name(cls, v):
        if not v.strip():
            raise ValueError("Table name cannot be empty")
        # Expected format: database.schema.table
        parts = v.split('.')
        if len(parts) != 3:
            raise ValueError("Table name must be fully qualified (database.schema.table)")
        return v.strip().upper()

class ReadQuerySchema(BaseModel):
    query: str
    max_rows: int = 1000
    
    @validator('query')
    def validate_query(cls, v):
        if not v.strip():
            raise ValueError("Query cannot be empty")
        return v.strip()
    
    @validator('max_rows')
    def validate_max_rows(cls, v):
        if v < 1 or v > settings.max_query_rows_limit:
            raise ValueError(f"max_rows must be between 1 and {settings.max_query_rows_limit}")
        return v

class AppendInsightSchema(BaseModel):
    insight: str
    
    @validator('insight')
    def validate_insight(cls, v):
        if not v.strip():
            raise ValueError("Insight cannot be empty")
        return v.strip()

def get_snowflake_tools() -> List[Tool]:
    """Return list of Snowflake tool definitions"""
    # Temporarily disabled - only query_payments is exposed to LLM
    # Uncomment the return statement below to re-enable these tools
    return []
    
    # Original tools - preserved for future use
    """
    return [
        Tool(
            name="list_databases",
            description="List all available databases",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="list_schemas", 
            description="List schemas in a database",
            inputSchema={
                "type": "object",
                "properties": {
                    "database": {"type": "string", "description": "Database name"}
                },
                "required": ["database"]
            }
        ),
        Tool(
            name="list_tables",
            description="List tables in a database schema", 
            inputSchema={
                "type": "object",
                "properties": {
                    "database": {"type": "string", "description": "Database name"},
                    "schema": {"type": "string", "description": "Schema name"}
                },
                "required": ["database", "schema"]
            }
        ),
        Tool(
            name="describe_table",
            description="Get detailed table schema",
            inputSchema={
                "type": "object", 
                "properties": {
                    "table_name": {"type": "string", "description": "Fully qualified table name (database.schema.table)"}
                },
                "required": ["table_name"]
            }
        ),
        Tool(
            name="read_query", 
            description="Execute read-only SQL query",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "SQL SELECT query to execute"},
                    "max_rows": {"type": "integer", "description": "Maximum number of rows to return", "default": 1000}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="append_insight",
            description="Log a data insight", 
            inputSchema={
                "type": "object",
                "properties": {
                    "insight": {"type": "string", "description": "Data insight to log"}
                },
                "required": ["insight"]
            }
        )
    ]
    """

async def handle_snowflake_tool(tool_name: str, arguments: Dict[str, Any], bearer_token: str = None, raw_request: str = None) -> List[TextContent]:
    """Handle Snowflake tool calls with timing and pre/post logging"""
    import uuid
    
    # Generate unique request ID to link pre and post entries
    request_id = str(uuid.uuid4())
    
    # Log pre-processing stage with raw request
    start_time = time.time()
    await log_activity(
        tool_name=tool_name,
        arguments=arguments,
        processing_stage="pre",
        raw_request=raw_request,
        bearer_token=bearer_token,
        request_id=request_id
    )
    
    try:
        if tool_name == "list_databases":
            result = await list_databases_handler(arguments, bearer_token, request_id)
        elif tool_name == "list_schemas":
            result = await list_schemas_handler(arguments, bearer_token, request_id)
        elif tool_name == "list_tables":
            result = await list_tables_handler(arguments, bearer_token, request_id)
        elif tool_name == "describe_table":
            result = await describe_table_handler(arguments, bearer_token, request_id)
        elif tool_name == "read_query":
            result = await read_query_handler(arguments, bearer_token, request_id)
        elif tool_name == "append_insight":
            result = await append_insight_handler(arguments, bearer_token, request_id)
        else:
            result = [TextContent(type="text", text=f"Unknown Snowflake tool: {tool_name}")]
        
        # Calculate execution time
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # Post-processing logging is done in individual handlers with row counts
        # but we'll pass the execution time through
        return result
        
    except Exception as error:
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # Log post-processing stage with error
        await log_activity(
            tool_name=tool_name,
            arguments=arguments,
            processing_stage="post",
            execution_success=False,
            execution_time_ms=execution_time_ms,
            bearer_token=bearer_token,
            request_id=request_id
        )
        
        logging.error(f"Error in {tool_name}: {error}")
        return [TextContent(type="text", text=f"Error: {str(error)}")]

# Tool handler functions
async def list_databases_handler(arguments: Dict[str, Any], bearer_token: str = None, request_id: str = None) -> List[TextContent]:
    """List all available databases"""
    start_time = time.time()
    try:
        conn = get_environment_snowflake_connection()
        cursor = conn.cursor()
        cursor.execute("SHOW DATABASES")
        databases = cursor.fetchall()
        
        db_list = [{"name": db[1], "owner": db[3], "created_on": str(db[2])} for db in databases]
        cursor.close()
        conn.close()
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        await log_activity(
            "list_databases", 
            arguments, 
            len(db_list),
            execution_time_ms=execution_time_ms,
            processing_stage="post",
            bearer_token=bearer_token,
            request_id=request_id
        )
        
        # Use clean formatting
        from utils.response_formatters import format_list_results
        clean_result = format_list_results(db_list, "databases")
        return [TextContent(type="text", text=clean_result)]
        
    except Exception as error:
        logging.error(f"list_databases error: {error}")
        return [TextContent(type="text", text=f"Failed to list databases: {str(error)}")]

async def list_schemas_handler(arguments: Dict[str, Any], bearer_token: str = None, request_id: str = None) -> List[TextContent]:
    """List schemas in a database"""
    start_time = time.time()
    try:
        params = ListSchemasSchema(**arguments)
        
        conn = get_environment_snowflake_connection()
        cursor = conn.cursor()
        cursor.execute(f"SHOW SCHEMAS IN DATABASE {params.database}")
        schemas = cursor.fetchall()
        
        schema_list = [{"name": schema[1], "owner": schema[3], "created_on": str(schema[2])} for schema in schemas]
        cursor.close()
        conn.close()
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        await log_activity(
            "list_schemas", 
            arguments, 
            len(schema_list),
            execution_time_ms=execution_time_ms,
            processing_stage="post",
            bearer_token=bearer_token,
            request_id=request_id
        )
        
        # Use clean formatting
        from utils.response_formatters import format_list_results
        clean_result = format_list_results(schema_list, f"schemas in {params.database}")
        return [TextContent(type="text", text=clean_result)]
        
    except Exception as error:
        logging.error(f"list_schemas error: {error}")
        return [TextContent(type="text", text=f"Failed to list schemas: {str(error)}")]

async def list_tables_handler(arguments: Dict[str, Any], bearer_token: str = None, request_id: str = None) -> List[TextContent]:
    """List tables in a database schema"""
    start_time = time.time()
    try:
        params = ListTablesSchema(**arguments)
        
        conn = get_environment_snowflake_connection()
        cursor = conn.cursor()
        cursor.execute(f"SHOW TABLES IN SCHEMA {params.database}.{params.schema}")
        tables = cursor.fetchall()
        
        table_list = [{"name": table[1], "owner": table[3], "created_on": str(table[2]), "rows": table[5]} for table in tables]
        cursor.close()
        conn.close()
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        await log_activity(
            "list_tables", 
            arguments, 
            len(table_list),
            execution_time_ms=execution_time_ms,
            processing_stage="post",
            bearer_token=bearer_token,
            request_id=request_id
        )
        
        # Use clean formatting  
        from utils.response_formatters import format_list_results
        clean_result = format_list_results(table_list, f"tables in {params.database}.{params.schema}")
        return [TextContent(type="text", text=clean_result)]
        
    except Exception as error:
        logging.error(f"list_tables error: {error}")
        return [TextContent(type="text", text=f"Failed to list tables: {str(error)}")]

async def describe_table_handler(arguments: Dict[str, Any], bearer_token: str = None, request_id: str = None) -> List[TextContent]:
    """Get detailed table schema"""
    start_time = time.time()
    try:
        params = DescribeTableSchema(**arguments)
        
        conn = get_environment_snowflake_connection()
        cursor = conn.cursor()
        cursor.execute(f"DESCRIBE TABLE {params.table_name}")
        columns = cursor.fetchall()
        
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
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        await log_activity(
            "describe_table", 
            arguments, 
            len(column_list),
            execution_time_ms=execution_time_ms,
            processing_stage="post",
            bearer_token=bearer_token,
            request_id=request_id
        )
        
        # Use clean formatting
        from utils.response_formatters import format_schema_results
        clean_result = format_schema_results(column_list, params.table_name)
        return [TextContent(type="text", text=clean_result)]
        
    except Exception as error:
        logging.error(f"describe_table error: {error}")
        return [TextContent(type="text", text=f"Failed to describe table: {str(error)}")]

async def read_query_handler(arguments: Dict[str, Any], bearer_token: str = None, request_id: str = None, is_internal: bool = False) -> List[TextContent]:
    """Execute a read-only SQL query against Snowflake"""
    start_time = time.time()
    try:
        params = ReadQuerySchema(**arguments)
        
        # Validate SQL query for security
        validation = SqlValidator.validate_sql_query(params.query)
        if not validation.is_valid:
            return [TextContent(type="text", text=f"Invalid SQL query: {validation.error}")]
        
        conn = get_environment_snowflake_connection()
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
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        await log_activity(
            "read_query", 
            {"query": params.query}, 
            len(result_list),
            execution_time_ms=execution_time_ms,
            processing_stage="post",
            bearer_token=bearer_token,
            request_id=request_id,
            action_type="internal_tool_call" if is_internal else None
        )
        
        # Return raw data for internal calls, formatted for external
        if is_internal:
            # Return raw JSON data for internal processing
            import json
            raw_json = json.dumps(result_list, default=str)
            return [TextContent(type="text", text=f"{len(result_list)} rows returned: {raw_json}")]
        else:
            # Use clean formatting for external calls
            from utils.response_formatters import format_table_results
            clean_result = format_table_results(result_list, f"Query: {params.query}")
            return [TextContent(type="text", text=clean_result)]
        
    except Exception as error:
        logging.error(f"read_query error: {error}")
        return [TextContent(type="text", text=f"Query execution failed: {SqlValidator.format_database_error(error)}")]

async def append_insight_handler(arguments: Dict[str, Any], bearer_token: str = None, request_id: str = None) -> List[TextContent]:
    """Add a data insight to the insights memo"""
    start_time = time.time()
    try:
        params = AppendInsightSchema(**arguments)
        
        # For now, just return success - in production this would append to a memo resource
        execution_time_ms = int((time.time() - start_time) * 1000)
        await log_activity(
            "append_insight", 
            arguments, 
            1,
            execution_time_ms=execution_time_ms,
            processing_stage="post",
            bearer_token=bearer_token,
            request_id=request_id
        )
        
        result = f"Insight recorded successfully: {params.insight}"
        return [TextContent(type="text", text=result)]
        
    except Exception as error:
        logging.error(f"append_insight error: {error}")
        return [TextContent(type="text", text=f"Failed to record insight: {str(error)}")]