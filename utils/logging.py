import json
import logging
import hashlib
from typing import Dict, Any, Optional
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
    bearer_token: Optional[str] = None
):
    """Log MCP tool activity to AI_USER_ACTIVITY_LOG"""
    try:
        conn = get_environment_snowflake_connection()
        
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
        
        # Build ACTION_DETAILS object with all context
        action_details_obj = {
            "tool_name": tool_name,
            "arguments": arguments,
            "row_count": row_count,
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
            EXECUTION_TIME_MS
        )
        SELECT 
            %s as USER_EMAIL,
            %s as ACTION_TYPE,
            %s as ENTITY_TYPE,
            %s as ENTITY_ID,
            PARSE_JSON(%s) as ACTION_DETAILS,
            %s as SUCCESS,
            %s as EXECUTION_TIME_MS
        """
        
        # Convert dict to JSON string for Snowflake OBJECT column
        action_details_json = json.dumps(action_details_obj)
        
        cursor.execute(insert_sql, (
            'mcp_server@popfly.com',  # Generic email for MCP server
            'tool_execution',
            'mcp_tool',
            tool_name,
            action_details_json,  # JSON string that will be converted by PARSE_JSON()
            execution_success,
            execution_time_ms
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