import json
import logging
import time
from typing import Dict, Any, List
from mcp.types import Tool, TextContent
from pydantic import BaseModel, validator

from cortex.cortex_generator import CortexGenerator, CortexRequest
from utils.logging import log_activity

class QueryPaymentsSchema(BaseModel):
    query: str
    max_rows: int = 1000
    
    @validator('query')
    def validate_query(cls, v):
        if not v.strip():
            raise ValueError("Natural language query cannot be empty")
        return v.strip()
    
    @validator('max_rows')
    def validate_max_rows(cls, v):
        if v < 1 or v > 10000:
            raise ValueError("max_rows must be between 1 and 10000")
        return v

def get_cortex_tools() -> List[Tool]:
    """Return list of Cortex tool definitions"""
    return [
        Tool(
            name="query_payments",
            description="Query payment data using natural language (powered by Snowflake Cortex)",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string", 
                        "description": "Natural language query about payments (e.g., 'Show me payments over $1000 from last month')"
                    },
                    "max_rows": {
                        "type": "integer", 
                        "description": "Maximum number of rows to return",
                        "default": 1000
                    }
                },
                "required": ["query"]
            }
        )
    ]

async def handle_cortex_tool(tool_name: str, arguments: Dict[str, Any], bearer_token: str = None, raw_request: str = None) -> List[TextContent]:
    """Handle Cortex tool calls with timing and pre/post logging"""
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
        if tool_name == "query_payments":
            result = await query_payments_handler(arguments, bearer_token, start_time, request_id)
        else:
            result = [TextContent(type="text", text=f"Unknown Cortex tool: {tool_name}")]
        
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

async def query_payments_handler(arguments: Dict[str, Any], bearer_token: str = None, start_time: float = None, request_id: str = None) -> List[TextContent]:
    """Query payment data using natural language via Snowflake Cortex"""
    if start_time is None:
        start_time = time.time()
    
    try:
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
            execution_time_ms = int((time.time() - start_time) * 1000)
            await log_activity(
                "query_payments", 
                arguments, 
                0, 
                execution_success=False, 
                natural_query=params.query,
                execution_time_ms=execution_time_ms,
                processing_stage="post",
                bearer_token=bearer_token,
                request_id=request_id
            )
            return [TextContent(type="text", text=f"Failed to generate SQL: {cortex_response.error}")]
        
        # Execute the generated SQL
        from tools.snowflake_tools import read_query_handler
        sql_arguments = {
            "query": cortex_response.generated_sql,
            "max_rows": params.max_rows
        }
        
        # Execute the query (pass bearer_token for consistent logging)
        sql_results = await read_query_handler(sql_arguments, bearer_token, request_id)
        
        # Calculate execution time and log the activity
        execution_time_ms = int((time.time() - start_time) * 1000)
        await log_activity(
            "query_payments", 
            arguments, 
            execution_success=cortex_response.success,
            natural_query=params.query,
            generated_sql=cortex_response.generated_sql,
            execution_time_ms=execution_time_ms,
            processing_stage="post",
            bearer_token=bearer_token,
            request_id=request_id
        )
        
        # Extract the actual data from the SQL results
        if sql_results and sql_results[0].text:
            # Parse the JSON results from the SQL response
            import re
            sql_text = sql_results[0].text
            
            # Extract JSON from the SQL result text
            if "rows returned:" in sql_text:
                json_match = re.search(r'rows returned:\s*(\[.*\])', sql_text, re.DOTALL)
                if json_match:
                    try:
                        import json
                        results_data = json.loads(json_match.group(1))
                        
                        # Use the payment formatter for clean results
                        from utils.response_formatters import format_payment_results
                        clean_result = format_payment_results(results_data, params.query)
                        
                        return [TextContent(type="text", text=clean_result)]
                    except json.JSONDecodeError:
                        pass
        
        # Fallback to simple no results message
        return [TextContent(type="text", text=f"**No Payment Records Found**\n\nNo payment records match your query: \"{params.query}\"")]
        
    except Exception as error:
        execution_time_ms = int((time.time() - start_time) * 1000)
        logging.error(f"query_payments error: {error}")
        await log_activity(
            "query_payments", 
            arguments, 
            0, 
            execution_success=False, 
            natural_query=arguments.get('query', ''),
            execution_time_ms=execution_time_ms,
            processing_stage="post",
            bearer_token=bearer_token,
            request_id=request_id
        )
        return [TextContent(type="text", text=f"Failed to process natural language query: {str(error)}")]