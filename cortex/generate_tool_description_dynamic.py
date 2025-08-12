#!/usr/bin/env python3
"""
Generate enriched tool descriptions dynamically from database metadata.
This replaces the hardcoded version with database-driven descriptions.
"""
import json
import logging
from typing import Dict, List, Optional, Any
from utils.config import get_environment_snowflake_connection

class DynamicToolDescriptionGenerator:
    """Generate tool descriptions from narrative metadata in database"""
    
    @staticmethod
    def generate_for_table(table_name: str = "MV_CREATOR_PAYMENTS_UNION") -> tuple[str, dict]:
        """
        Generate comprehensive tool description from database metadata.
        
        Returns:
            Tuple of (description_text, input_schema)
        """
        conn = get_environment_snowflake_connection()
        cursor = conn.cursor()
        
        try:
            # 1. Get business context
            # Map table name to domain
            domain = 'creator_payments' if 'CREATOR_PAYMENTS' in table_name else table_name.lower()
            
            cursor.execute("""
                SELECT bc.TITLE, bc.DESCRIPTION, bc.KEYWORDS, bc.EXAMPLES
                FROM PF.BI.AI_BUSINESS_CONTEXT bc
                WHERE bc.DOMAIN = %s
                ORDER BY bc.UPDATED_AT DESC
                LIMIT 1
            """, (domain,))
            
            business_context = cursor.fetchone()
            
            # 2. Get column metadata
            cursor.execute("""
                SELECT COLUMN_NAME, BUSINESS_MEANING, KEYWORDS, EXAMPLES
                FROM PF.BI.AI_SCHEMA_METADATA
                WHERE TABLE_NAME = %s
                ORDER BY 
                    CASE 
                        WHEN COLUMN_NAME LIKE '%%PAYMENT%%' THEN 1
                        WHEN COLUMN_NAME LIKE '%%CREATOR%%' THEN 2
                        WHEN COLUMN_NAME LIKE '%%COMPANY%%' THEN 3
                        ELSE 4
                    END,
                    COLUMN_NAME
            """, (table_name,))
            
            columns = cursor.fetchall()
            
            # 3. Get view constraints for additional context
            cursor.execute("""
                SELECT ALLOWED_OPERATIONS, FORBIDDEN_KEYWORDS, MAX_ROW_LIMIT, SECURITY_NOTES
                FROM PF.BI.AI_VIEW_CONSTRAINTS
                WHERE VIEW_NAME = %s
            """, (table_name,))
            
            constraints = cursor.fetchone()
            
            # Build the description
            description = DynamicToolDescriptionGenerator._build_description(
                business_context, columns, constraints, table_name
            )
            
            # Build the input schema
            input_schema = DynamicToolDescriptionGenerator._build_input_schema(
                business_context, constraints
            )
            
            cursor.close()
            conn.close()
            
            return description, input_schema
            
        except Exception as e:
            logging.error(f"Failed to generate dynamic tool description: {e}", exc_info=True)
            cursor.close()
            conn.close()
            # Fall back to a basic description
            return DynamicToolDescriptionGenerator._get_fallback_description()
    
    @staticmethod
    def _build_description(
        business_context: Optional[tuple], 
        columns: List[tuple],
        constraints: Optional[tuple],
        table_name: str
    ) -> str:
        """Build comprehensive description from metadata"""
        
        parts = []
        
        # Main purpose from business context
        if business_context:
            title, description, keywords_json, examples = business_context
            
            # Parse description for key information
            desc_lines = description.split('\n') if description else []
            
            # Extract purpose
            purpose = desc_lines[0] if desc_lines else "Query payment data using natural language"
            parts.append(purpose)
            
            # Extract payment types if present
            payment_types = []
            terminology = []
            for line in desc_lines:
                if 'Agency Mode' in line:
                    payment_types.append("• Agency Mode: " + line.split('Agency Mode:')[-1].strip())
                elif 'Direct Mode' in line:
                    payment_types.append("• Direct Mode: " + line.split('Direct Mode:')[-1].strip())
                elif 'Unassigned' in line:
                    payment_types.append("• Unassigned: " + line.split('Unassigned:')[-1].strip())
                elif '=' in line and any(term in line for term in ['Payment', 'Invoice', 'Transfer']):
                    terminology.append("• " + line.strip())
            
            if payment_types:
                parts.append("\nPAYMENT TYPES:")
                parts.extend(payment_types)
            
            # Build key entities from columns
            if columns:
                entities = DynamicToolDescriptionGenerator._extract_key_entities(columns)
                if entities:
                    parts.append("\nKEY ENTITIES YOU CAN QUERY:")
                    parts.extend(entities)
            
            # Add terminology if found
            if terminology:
                parts.append("\nUNDERSTANDS PAYMENT TERMINOLOGY:")
                parts.extend(terminology)
            
            # Add example queries
            if examples:
                example_lines = examples.split('\n')[:6]  # Limit to 6 examples
                if example_lines:
                    parts.append("\nEXAMPLE QUERIES:")
                    for ex in example_lines:
                        if ex.strip():
                            parts.append(f"• {ex.strip()}")
        else:
            parts.append("Query data using natural language powered by Snowflake Cortex AI.")
        
        # Add operational notes
        if constraints:
            allowed_ops, forbidden, max_rows, security_notes = constraints
            if max_rows:
                parts.append(f"\nDEFAULT LIMIT: {min(1000, max_rows)} rows")
            if security_notes:
                # Extract key info from security notes
                if 'January 2025' in security_notes:
                    parts.append("DATA COVERAGE: January 2025 onwards only (earlier data unreliable)")
        
        parts.append("TIMEZONE: UTC")
        
        return '\n'.join(parts)
    
    @staticmethod
    def _extract_key_entities(columns: List[tuple]) -> List[str]:
        """Extract key entities from column metadata"""
        entities = []
        
        # Group columns by entity type
        creator_cols = []
        company_cols = []
        campaign_cols = []
        payment_cols = []
        
        for col_name, meaning, keywords_json, examples in columns:
            col_upper = col_name.upper()
            
            if 'CREATOR' in col_upper or 'STRIPE_CONNECTED' in col_upper:
                creator_cols.append((col_name, meaning, examples))
            elif 'COMPANY' in col_upper or 'STRIPE_CUSTOMER' in col_upper:
                company_cols.append((col_name, meaning, examples))
            elif 'CAMPAIGN' in col_upper:
                campaign_cols.append((col_name, meaning, examples))
            elif 'PAYMENT' in col_upper or 'AMOUNT' in col_upper:
                payment_cols.append((col_name, meaning, examples))
        
        # Build entity descriptions
        if creator_cols:
            examples = [ex for _, _, ex in creator_cols if ex]
            entities.append(f"• Creators (by name, Stripe account, or user ID)")
        
        if company_cols:
            entities.append(f"• Companies/Customers (by name, Stripe customer ID)")
        
        if campaign_cols:
            entities.append(f"• Campaigns/Projects (by name)")
        
        if payment_cols:
            entities.append(f"• Payment amounts, dates, and statuses")
        
        return entities
    
    @staticmethod
    def _build_input_schema(
        business_context: Optional[tuple],
        constraints: Optional[tuple]
    ) -> dict:
        """Build input schema from metadata"""
        
        # Extract example queries from business context
        example_queries = []
        if business_context:
            _, _, _, examples = business_context
            if examples:
                example_lines = examples.split('\n')[:5]
                example_queries = [ex.strip() for ex in example_lines if ex.strip()]
        
        # Set max rows from constraints
        max_rows_limit = 10000
        if constraints:
            _, _, max_row_limit, _ = constraints
            if max_row_limit:
                max_rows_limit = max_row_limit
        
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query about payments, invoices, or transfers. Can reference creators, companies, campaigns, amounts, dates, payment types, and statuses.",
                    "examples": example_queries or [
                        "Show all payments over $1000",
                        "List pending invoices for a creator",
                        "Total payments by campaign",
                        "Which creators have been paid this month?",
                        "Unpaid invoices older than 30 days"
                    ]
                },
                "max_rows": {
                    "type": "integer",
                    "description": f"Maximum rows to return (1-{max_rows_limit}). Default 1000.",
                    "default": 1000,
                    "minimum": 1,
                    "maximum": max_rows_limit
                }
            },
            "required": ["query"],
            "additionalProperties": False
        }
    
    @staticmethod
    def _get_fallback_description() -> tuple[str, dict]:
        """Fallback description if database read fails"""
        description = """Query data using natural language. Powered by Snowflake Cortex AI.
        
This tool understands natural language queries and converts them to SQL.

DEFAULT LIMIT: 1000 rows
TIMEZONE: UTC"""
        
        schema = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query"
                },
                "max_rows": {
                    "type": "integer",
                    "default": 1000,
                    "minimum": 1,
                    "maximum": 10000
                }
            },
            "required": ["query"]
        }
        
        return description, schema


def update_tool_in_database(tool_name: str = "query_payments", table_name: str = "MV_CREATOR_PAYMENTS_UNION"):
    """Update tool description in AI_MCP_TOOLS with dynamic content"""
    
    # Generate dynamic description
    generator = DynamicToolDescriptionGenerator()
    description, input_schema = generator.generate_for_table(table_name)
    
    # Update in database
    conn = get_environment_snowflake_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE PF.BI.AI_MCP_TOOLS
            SET 
                TOOL_DESCRIPTION = %s,
                INPUT_SCHEMA = PARSE_JSON(%s),
                UPDATED_AT = CURRENT_TIMESTAMP()
            WHERE TOOL_NAME = %s
        """, (description, json.dumps(input_schema), tool_name))
        
        conn.commit()
        
        # Verify
        cursor.execute("""
            SELECT 
                TOOL_NAME,
                LENGTH(TOOL_DESCRIPTION) as DESC_LENGTH,
                UPDATED_AT
            FROM PF.BI.AI_MCP_TOOLS
            WHERE TOOL_NAME = %s
        """, (tool_name,))
        
        result = cursor.fetchone()
        print(f"Updated tool: {result[0]}")
        print(f"Description length: {result[1]} characters")
        print(f"Updated at: {result[2]}")
        
        cursor.close()
        conn.close()
        
        return description, input_schema
        
    except Exception as e:
        cursor.close()
        conn.close()
        raise e


if __name__ == "__main__":
    # Test the generator
    print("Generating dynamic tool description from database metadata...")
    description, schema = update_tool_in_database()
    print("\n=== Generated Description ===")
    print(description)
    print("\n=== Generated Schema ===")
    print(json.dumps(schema, indent=2))