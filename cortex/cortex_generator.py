import asyncio
import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import json

from utils.config import get_environment_snowflake_connection
from config.settings import settings
from validators.sql_validator import SqlValidator, SqlValidationResult
from utils.logging import log_cortex_usage
from utils.prompt_builder import PromptBuilder

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
    # Prompt metadata (optional)
    prompt_id: Optional[str] = None
    prompt_char_count: Optional[int] = None
    relevant_columns_k: Optional[int] = None

class CortexGenerator:
    """Snowflake Cortex SQL generation with security validation"""
    
    VIEW_CONSTRAINTS = {
        "V_CREATOR_PAYMENTS_UNION": {
            "allowed_operations": ["SELECT", "WHERE", "GROUP BY", "ORDER BY", "LIMIT", "HAVING"],
            "allowed_columns": [
                "USER_ID", "CREATOR_NAME", "COMPANY_NAME", "CAMPAIGN_NAME",
                "REFERENCE_TYPE", "REFERENCE_ID", "PAYMENT_TYPE", 
                "PAYMENT_AMOUNT", "PAYMENT_STATUS", "PAYMENT_DATE",
                "CREATED_DATE", "STRIPE_CUSTOMER_ID", "STRIPE_CUSTOMER_NAME",
                "STRIPE_CONNECTED_ACCOUNT_ID", "STRIPE_CONNECTED_ACCOUNT_NAME"
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
            
            # Build Cortex prompt (DB-driven with graceful fallback)
            built = PromptBuilder.build_prompt_for_view(
                view_name=request.view_name,
                user_query=request.natural_language_query,
                max_rows=request.max_rows,
                allowed_ops=constraints["allowed_operations"],
                allowed_columns=constraints["allowed_columns"],
            )
            prompt = built.prompt_text
            
            # Execute Cortex SQL generation (measure generation latency)
            import time
            start_gen = time.time()
            generated_sql = await cls.call_cortex_complete(prompt)
            generation_time_ms = int((time.time() - start_gen) * 1000)
            
            # Validate generated SQL
            validation_result = SqlValidator.validate_sql_query(generated_sql)
            
            # Log usage
            await log_cortex_usage(
                natural_query=request.natural_language_query,
                generated_sql=generated_sql,
                validation_passed=validation_result.is_valid,
                view_name=request.view_name,
                execution_time_ms=generation_time_ms
            )
            
            return CortexResponse(
                success=validation_result.is_valid,
                generated_sql=generated_sql,
                validation_result=validation_result,
                error=validation_result.error if not validation_result.is_valid else None,
                prompt_id=built.prompt_id,
                prompt_char_count=built.prompt_char_count,
                relevant_columns_k=built.relevant_columns_k
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
- USER_ID: NUMBER - Creator user identifier
- CREATOR_NAME, COMPANY_NAME, CAMPAIGN_NAME: TEXT
- REFERENCE_TYPE, REFERENCE_ID, PAYMENT_TYPE: TEXT  
- PAYMENT_AMOUNT: NUMBER - Payment amount
- PAYMENT_STATUS: TEXT (values: PAID, PENDING, FAILED, etc.)
- PAYMENT_DATE, CREATED_DATE: TIMESTAMP_NTZ - Payment and creation dates
- STRIPE_CUSTOMER_ID, STRIPE_CUSTOMER_NAME: TEXT - Stripe customer info
- STRIPE_CONNECTED_ACCOUNT_ID, STRIPE_CONNECTED_ACCOUNT_NAME: TEXT - Stripe account info

**Natural Language Query:** {request.natural_language_query}

Generate a single, executable SQL SELECT statement that answers the query:
"""
        
        return prompt.strip()

    @classmethod
    async def call_cortex_complete(cls, prompt: str) -> str:
        """Call Snowflake Cortex COMPLETE function"""
        try:
            conn = get_environment_snowflake_connection()
            
            cursor = conn.cursor()
            
            # Execute Cortex COMPLETE function - format with proper parameter passing
            cortex_sql = """
            SELECT SNOWFLAKE.CORTEX.COMPLETE(
                %s,
                %s
            ) as generated_sql
            """
            
            cursor.execute(cortex_sql, (settings.cortex_model, prompt))
            result = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            if result and result[0]:
                # Extract SQL from Cortex response (may need parsing)
                generated_sql = str(result[0]).strip()
                
                # Clean up common Cortex response formatting
                # Extract SQL from markdown code blocks if present
                import re
                sql_match = re.search(r'```sql\s*\n(.*?)\n```', generated_sql, re.DOTALL)
                if sql_match:
                    generated_sql = sql_match.group(1).strip()
                elif generated_sql.startswith('```sql'):
                    generated_sql = generated_sql.replace('```sql', '').replace('```', '')
                
                # Additional cleanup for various response formats
                generated_sql = generated_sql.strip()
                
                # Remove any leading/trailing quotes
                if generated_sql.startswith('"') and generated_sql.endswith('"'):
                    generated_sql = generated_sql[1:-1]
                if generated_sql.startswith("'") and generated_sql.endswith("'"):
                    generated_sql = generated_sql[1:-1]
                
                # Clean up any remaining newlines and extra spaces
                generated_sql = ' '.join(generated_sql.split())
                
                # Log what we got for debugging
                logging.info(f"Cleaned SQL from Cortex: {repr(generated_sql)}")
                
                return generated_sql.strip()
            else:
                raise ValueError("Cortex returned empty response")
            
        except Exception as error:
            logging.error(f"Cortex COMPLETE call failed: {error}")
            raise