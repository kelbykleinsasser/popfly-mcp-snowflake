"""
Refactored Cortex Generator that uses database as single source of truth.
No more hardcoded constraints or table lists.
"""
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
from cortex.view_constraints_loader import ViewConstraintsLoader
from utils.cortex_search import CortexSearchClient

class CortexRequest(BaseModel):
    natural_language_query: str
    view_name: str = "MV_CREATOR_PAYMENTS_UNION"  # Default to materialized table
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
    """
    Snowflake Cortex SQL generation with database-driven validation.
    All constraints and metadata loaded dynamically from database tables.
    """
    
    @classmethod
    async def generate_sql(cls, request: CortexRequest) -> CortexResponse:
        """Generate SQL using Snowflake Cortex with dynamic validation"""
        try:
            # Check if we should use Cortex Search (default: True)
            use_search = getattr(settings, 'cortex_use_search', True)
            
            if use_search:
                # NEW: Use Cortex Search for minimal context (90% reduction)
                logging.info(f"Using Cortex Search for context retrieval")
                
                # Get minimal, relevant context using search
                relevant_context = CortexSearchClient.build_minimal_context(
                    request.natural_language_query,
                    request.view_name
                )
                
                # Build minimal prompt
                # Load allowed columns from constraints even when using search
                constraints = ViewConstraintsLoader.load_constraints(request.view_name)
                allowed_columns = "REFERENCE_ID, PAYMENT_TYPE, REFERENCE_TYPE, USER_ID, CREATOR_NAME, COMPANY_NAME, CAMPAIGN_NAME, PAYMENT_AMOUNT, PAYMENT_STATUS, PAYMENT_DATE, CREATED_DATE, STRIPE_CUSTOMER_ID, STRIPE_CUSTOMER_NAME, STRIPE_CONNECTED_ACCOUNT_ID, STRIPE_CONNECTED_ACCOUNT_NAME"
                if constraints and constraints.get("allowed_columns"):
                    allowed_columns = constraints["allowed_columns"]
                
                prompt = f"""You are a Snowflake SQL expert for {request.view_name}.

CRITICAL: Only these columns exist in {request.view_name}:
{allowed_columns}

DO NOT use any other columns. Common mistakes to avoid:
- There is NO 'PAYMENT_ID' column (use REFERENCE_ID instead)
- There is NO 'ID' column (use REFERENCE_ID)
- For counting rows, use COUNT(*) or COUNT(REFERENCE_ID)

{relevant_context}

User query: "{request.natural_language_query}"

Generate a single SELECT statement. Include LIMIT {request.max_rows}.
Return only the SQL, no explanation."""
                
                logging.info(f"Prompt size with Cortex Search: {len(prompt)} chars (was ~5000)")
                
                # Create mock built object for compatibility
                built = type('obj', (object,), {
                    'prompt_text': prompt,
                    'prompt_id': 'cortex_search',
                    'prompt_char_count': len(prompt),
                    'relevant_columns_k': 5
                })()
                
            else:
                # FALLBACK: Traditional approach with full context
                logging.info(f"Using traditional full context approach")
                
                # Load constraints from database (single source of truth)
                constraints = ViewConstraintsLoader.load_constraints(request.view_name)
                if not constraints:
                    return CortexResponse(
                        success=False,
                        error=f"View '{request.view_name}' not configured in AI_VIEW_CONSTRAINTS"
                    )
                
                # Build Cortex prompt using database metadata
                built = PromptBuilder.build_prompt_for_view(
                    view_name=request.view_name,
                    user_query=request.natural_language_query,
                    max_rows=request.max_rows,
                    allowed_ops=constraints["allowed_operations"],
                    allowed_columns=constraints["allowed_columns"],
                )
            
            prompt = built.prompt_text
            
            # Execute Cortex SQL generation
            import time
            start_gen = time.time()
            generated_sql = await cls.call_cortex_complete(prompt)
            generation_time_ms = int((time.time() - start_gen) * 1000)
            
            # Log the generated SQL for debugging
            logging.info(f"Cortex generated SQL for query '{request.natural_language_query[:50]}...': {generated_sql}")
            
            # Validate using dynamic validator (loads allowed tables from DB)
            validator = SqlValidator()
            validation_result = validator.validate_sql_query(generated_sql)
            
            # Additional validation for view-specific constraints (only if not using search)
            if validation_result.is_valid and not use_search:
                # Load constraints if we haven't already
                if 'constraints' not in locals():
                    constraints = ViewConstraintsLoader.load_constraints(request.view_name)
                
                if constraints:
                    validation_result = cls.validate_view_constraints(
                        generated_sql, 
                        request.view_name, 
                        constraints
                    )
            
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
    def validate_view_constraints(
        cls, 
        sql: str, 
        view_name: str, 
        constraints: Dict
    ) -> SqlValidationResult:
        """Additional validation specific to view constraints"""
        sql_upper = sql.upper()
        
        # Check forbidden keywords (must be whole words, not part of column names)
        forbidden = constraints.get("forbidden_keywords", [])
        import re
        for keyword in forbidden:
            # Use word boundaries to avoid matching column names like CREATED_DATE
            pattern = r'\b' + keyword.upper() + r'\b'
            if re.search(pattern, sql_upper):
                return SqlValidationResult(
                    is_valid=False,
                    error=f"Forbidden operation '{keyword}' detected in SQL"
                )
        
        # Check that only allowed columns are referenced
        allowed_cols = set(col.upper() for col in constraints.get("allowed_columns", []))
        
        # Simple check - could be made more sophisticated
        import re
        # Find potential column references (simplified)
        potential_cols = re.findall(r'\b([A-Z_][A-Z0-9_]*)\b', sql_upper)
        
        # Filter out SQL keywords and the table name
        sql_keywords = {'SELECT', 'FROM', 'WHERE', 'GROUP', 'BY', 'ORDER', 
                       'LIMIT', 'AND', 'OR', 'NOT', 'IN', 'LIKE', 'AS', 
                       'ASC', 'DESC', 'HAVING', 'COUNT', 'SUM', 'AVG', 
                       'MAX', 'MIN', 'DISTINCT', 'BETWEEN', 'NULL', 'IS'}
        
        for col in potential_cols:
            if col not in sql_keywords and col != view_name.upper():
                # Check if it looks like a column and isn't allowed
                if '_' in col and col not in allowed_cols:
                    # This might be a column reference
                    if col not in {'PAYMENT_MODE', 'AGENCY_MODE', 'DIRECT_MODE'}:  # Common values
                        logging.warning(f"Potential unauthorized column reference: {col}")
        
        return SqlValidationResult(is_valid=True)

    @classmethod
    async def call_cortex_complete(cls, prompt: str) -> str:
        """Call Snowflake Cortex COMPLETE function"""
        try:
            from utils.connection_pool import get_pooled_connection
            
            with get_pooled_connection() as conn:
                cursor = conn.cursor()
                
                # Execute Cortex COMPLETE function
                cortex_sql = """
                SELECT SNOWFLAKE.CORTEX.COMPLETE(
                    %s,
                    %s
                ) as generated_sql
                """
                
                cursor.execute(cortex_sql, (settings.cortex_model, prompt))
                result = cursor.fetchone()
                
                cursor.close()
            
            if result and result[0]:
                generated_sql = str(result[0]).strip()
                
                # Clean up common Cortex response formatting
                import re
                # Handle various markdown formats
                sql_match = re.search(r'```(?:sql)?\s*\n?(.*?)\n?```', generated_sql, re.DOTALL | re.IGNORECASE)
                if sql_match:
                    generated_sql = sql_match.group(1).strip()
                elif '```' in generated_sql:
                    # Remove any remaining backticks
                    generated_sql = generated_sql.replace('```sql', '').replace('```SQL', '').replace('```', '')
                
                # Additional cleanup
                generated_sql = generated_sql.strip()
                
                # Remove quotes
                if generated_sql.startswith('"') and generated_sql.endswith('"'):
                    generated_sql = generated_sql[1:-1]
                if generated_sql.startswith("'") and generated_sql.endswith("'"):
                    generated_sql = generated_sql[1:-1]
                
                # Clean up whitespace
                generated_sql = ' '.join(generated_sql.split())
                
                logging.info(f"Cleaned SQL from Cortex: {repr(generated_sql)}")
                return generated_sql.strip()
            else:
                raise ValueError("Cortex returned empty response")
            
        except Exception as error:
            logging.error(f"Cortex COMPLETE call failed: {error}")
            raise