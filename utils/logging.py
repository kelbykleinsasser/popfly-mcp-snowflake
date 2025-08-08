import json
import logging
import hashlib
import uuid
from typing import Dict, Any, Optional, Literal
from datetime import datetime

from utils.config import get_environment_snowflake_connection
from config.settings import settings

async def log_activity(
    tool_name: str,
    arguments: Dict[str, Any],
    row_count: int = 0,
    execution_success: bool = True,
    execution_time_ms: Optional[int] = None,
    natural_query: Optional[str] = None,
    generated_sql: Optional[str] = None,
    bearer_token: Optional[str] = None,
    processing_stage: Literal["pre", "post"] = "post",
    raw_request: Optional[str] = None,
    request_id: Optional[str] = None
):
    """Log MCP tool activity to AI_USER_ACTIVITY_LOG
    
    Args:
        tool_name: Name of the MCP tool being executed
        arguments: Arguments passed to the tool
        row_count: Number of rows affected/returned
        execution_success: Whether execution succeeded
        execution_time_ms: Time taken to execute in milliseconds
        natural_query: Natural language query (for Cortex tools)
        generated_sql: Generated SQL (for Cortex tools)
        bearer_token: Bearer token for authentication
        processing_stage: "pre" for raw request logging, "post" for after processing
        raw_request: Raw request string (for pre-processing stage)
        request_id: Unique ID to link pre and post processing entries
    """
    try:
        conn = get_environment_snowflake_connection()
        
        cursor = conn.cursor()
        
        # Hash bearer token for privacy
        bearer_token_hash = None
        if bearer_token:
            bearer_token_hash = hashlib.sha256(bearer_token.encode()).hexdigest()[:16]
        
        # Build ACTION_DETAILS object with context that's not in dedicated columns
        action_details_obj = {
            "tool_name": tool_name,
            "arguments": arguments if processing_stage == "post" else None,
            "row_count": row_count if processing_stage == "post" else None,
            "natural_query": natural_query,
            "generated_sql": generated_sql,
            "bearer_token_hash": bearer_token_hash
        }
        
        # Use INSERT...SELECT pattern for OBJECT columns
        insert_sql = """
        INSERT INTO AI_USER_ACTIVITY_LOG (
            USER_EMAIL,
            ACTION_TYPE,
            ENTITY_TYPE,
            ENTITY_ID,
            ACTION_DETAILS,
            SUCCESS,
            EXECUTION_TIME_MS,
            PROCESSING_STAGE,
            RAW_REQUEST,
            REQUEST_ID
        )
        SELECT 
            %s as USER_EMAIL,
            %s as ACTION_TYPE,
            %s as ENTITY_TYPE,
            %s as ENTITY_ID,
            PARSE_JSON(%s) as ACTION_DETAILS,
            %s as SUCCESS,
            %s as EXECUTION_TIME_MS,
            %s as PROCESSING_STAGE,
            PARSE_JSON(%s) as RAW_REQUEST,
            %s as REQUEST_ID
        """
        
        # Convert dict to JSON string for Snowflake OBJECT column
        action_details_json = json.dumps(action_details_obj)
        
        # Convert raw_request to JSON string for VARIANT column (or None)
        raw_request_json = raw_request if raw_request else None
        
        # Keep ACTION_TYPE simple, use PROCESSING_STAGE column for stage info
        action_type = "tool_execution"
        
        cursor.execute(insert_sql, (
            'mcp_server@popfly.com',  # Generic email for MCP server
            action_type,
            'mcp_tool',
            tool_name,
            action_details_json,  # JSON string that will be converted by PARSE_JSON()
            execution_success,
            execution_time_ms,
            processing_stage,
            raw_request_json,  # Raw request JSON string or None
            request_id
        ))
        
        # Ensure the insert is committed
        conn.commit()
        
        cursor.close()
        conn.close()
        
        logging.debug(f"Successfully logged activity for tool: {tool_name}")
        
    except Exception as error:
        # Log the full error with stack trace for debugging
        logging.error(f"Failed to log activity for tool '{tool_name}': {error}", exc_info=True)
        
        # In production, also try to write to a fallback log
        if settings.environment == 'production':
            logging.error(f"Activity log fallback - Tool: {tool_name}, Args: {arguments}, Success: {execution_success}")

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
        conn = get_environment_snowflake_connection()
        
        cursor = conn.cursor()
        
        insert_sql = """
        INSERT INTO AI_CORTEX_USAGE_LOG (
            USER_EMAIL,
            FUNCTION_NAME,
            QUERY_TEXT,
            SUCCESS,
            TOKENS_USED,
            EXECUTION_TIME_MS
        ) VALUES (
            %s, %s, %s, %s, %s, %s
        )
        """
        
        cursor.execute(insert_sql, (
            'mcp_server@popfly.com',
            'COMPLETE',  # Using COMPLETE function
            natural_query,
            validation_passed,
            credits_used,  # Using as token approximation
            execution_time_ms
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