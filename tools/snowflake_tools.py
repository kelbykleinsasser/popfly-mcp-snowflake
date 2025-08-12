import json
import logging
import time
from typing import Dict, Any, List
from mcp.types import Tool, TextContent
from pydantic import BaseModel, validator

from utils.config import get_environment_snowflake_connection
from utils.connection_pool import get_pooled_connection
from config.settings import settings
from validators.sql_validator import SqlValidator
from utils.response_helpers import create_success_response, create_error_response
from utils.logging import log_activity

# Pydantic schemas for input validation
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

def get_snowflake_tools() -> List[Tool]:
    """Return list of Snowflake tool definitions"""
    # All tools are now loaded dynamically from database
    # No hardcoded definitions - if database is down, no tools available
    return []

# Tool handler functions
async def read_query_handler(arguments: Dict[str, Any], bearer_token: str = None, request_id: str = None, is_internal: bool = False) -> List[TextContent]:
    """Execute a read-only SQL query against Snowflake"""
    start_time = time.time()
    try:
        params = ReadQuerySchema(**arguments)
        
        # Validate SQL query for security
        validation = SqlValidator.validate_sql_query(params.query)
        if not validation.is_valid:
            return [TextContent(type="text", text=f"Invalid SQL query: {validation.error}")]
        
        # Use connection pool
        with get_pooled_connection() as conn:
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

