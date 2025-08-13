"""
Payment-related tools for MCP Server
These handlers are called by the dynamic tool registry
"""
import json
import logging
import re
import time
from typing import Dict, Any, List
from mcp.types import TextContent
from pydantic import BaseModel, validator

from cortex.cortex_generator_v2 import CortexGenerator, CortexRequest
from tools.snowflake_tools import read_query_handler
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


async def query_payments_handler(arguments: Dict[str, Any], bearer_token: str = None, request_id: str = None) -> List[TextContent]:
    """Query payment data using natural language via Snowflake Cortex"""
    import uuid
    
    # Generate request ID if not provided
    if request_id is None:
        request_id = str(uuid.uuid4())
    
    start_time = time.time()
    
    # Log pre-processing stage
    await log_activity(
        tool_name="query_payments",
        arguments=arguments,
        processing_stage="pre",
        bearer_token=bearer_token,
        request_id=request_id,
        natural_query=arguments.get('query')
    )
    
    try:
        params = QueryPaymentsSchema(**arguments)
        
        # Create Cortex request (using materialized table, not view)
        cortex_request = CortexRequest(
            natural_language_query=params.query,
            view_name="MV_CREATOR_PAYMENTS_UNION",  # Note: This is actually a table, not a view
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
        sql_arguments = {
            "query": cortex_response.generated_sql,
            "max_rows": params.max_rows
        }
        
        # Log the generated SQL for debugging
        logging.info(f"[{request_id[:8]}] Executing Cortex-generated SQL: {cortex_response.generated_sql}")
        
        # Execute the query (pass bearer_token for consistent logging, mark as internal)
        sql_results = await read_query_handler(sql_arguments, bearer_token, request_id, is_internal=True)
        
        # Calculate execution time - but don't log yet, we need to count rows first
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # Extract the actual data from the SQL results
        row_count = 0
        if sql_results and sql_results[0].text:
            # Parse the JSON results from the SQL response
            sql_text = sql_results[0].text
            
            # Log the raw SQL result for debugging
            logging.info(f"SQL result text (first 500 chars): {sql_text[:500]}")
            
            # Extract JSON from the SQL result text
            if "rows returned:" in sql_text:
                logging.info(f"Found 'rows returned' in SQL text")
                json_match = re.search(r'\d+\s+rows returned:\s*(\[.*\])', sql_text, re.DOTALL)
                if json_match:
                    logging.info(f"Regex matched! Group 1 length: {len(json_match.group(1))}")
                    try:
                        results_data = json.loads(json_match.group(1))
                        row_count = len(results_data)  # Count actual results
                        
                        # Add temporal context to the response
                        # Check if the query or SQL references current time periods
                        import datetime
                        current_date = datetime.datetime.now()
                        
                        # Detect if query is about current time period
                        time_context = ""
                        query_lower = params.query.lower()
                        sql_lower = cortex_response.generated_sql.lower() if cortex_response.generated_sql else ""
                        
                        logging.info(f"Checking for temporal context - Query: '{query_lower[:50]}...', SQL has CURRENT_DATE: {'current_date' in sql_lower}")
                        
                        if "current_date" in sql_lower or "current_timestamp" in sql_lower:
                            # Add explicit temporal context
                            if "this month" in query_lower or "current month" in query_lower:
                                time_context = f"\n\n**Time Period: {current_date.strftime('%B %Y')}**"
                            elif "today" in query_lower:
                                time_context = f"\n\n**Date: {current_date.strftime('%B %d, %Y')}**"
                            elif "this year" in query_lower or "current year" in query_lower:
                                time_context = f"\n\n**Year: {current_date.year}**"
                            elif "this week" in query_lower:
                                time_context = f"\n\n**Week of: {current_date.strftime('%B %d, %Y')}**"
                        
                        # Return JSON with temporal context and query info
                        clean_result = json.dumps(results_data, indent=2)
                        
                        # Add metadata footer with temporal context
                        metadata_parts = []
                        if time_context:
                            metadata_parts.append(time_context)
                        
                        # Add SQL query for transparency
                        if cortex_response.generated_sql:
                            metadata_parts.append(f"\n**Generated SQL:** `{cortex_response.generated_sql}`")
                        
                        if metadata_parts:
                            clean_result = clean_result + "\n" + "".join(metadata_parts)
                        
                        # Log the successful activity with actual row count
                        await log_activity(
                            "query_payments", 
                            {
                                **arguments,
                                "prompt_id": cortex_response.prompt_id,
                                "prompt_char_count": cortex_response.prompt_char_count,
                                "relevant_columns_k": cortex_response.relevant_columns_k,
                            }, 
                            row_count=row_count,
                            execution_success=True,
                            natural_query=params.query,
                            generated_sql=cortex_response.generated_sql,
                            execution_time_ms=execution_time_ms,
                            processing_stage="post",
                            bearer_token=bearer_token,
                            request_id=request_id
                        )
                        
                        return [TextContent(type="text", text=clean_result)]
                    except json.JSONDecodeError:
                        pass
        
        # Fallback to simple no results message
        # Log activity with 0 rows if we reach here
        await log_activity(
            "query_payments", 
            {
                **arguments,
                "prompt_id": cortex_response.prompt_id if 'cortex_response' in locals() else None,
                "prompt_char_count": cortex_response.prompt_char_count if 'cortex_response' in locals() else None,
                "relevant_columns_k": cortex_response.relevant_columns_k if 'cortex_response' in locals() else None,
            }, 
            row_count=0,
            execution_success=True,
            natural_query=params.query,
            generated_sql=cortex_response.generated_sql if 'cortex_response' in locals() else None,
            execution_time_ms=execution_time_ms,
            processing_stage="post",
            bearer_token=bearer_token,
            request_id=request_id
        )
        
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