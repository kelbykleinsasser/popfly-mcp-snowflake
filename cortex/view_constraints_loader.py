"""
Load view constraints from database instead of hardcoding them.
This ensures AI_VIEW_CONSTRAINTS is the single source of truth.
"""
import logging
from typing import Dict, List, Optional, Any
from utils.config import get_environment_snowflake_connection

class ViewConstraintsLoader:
    """Load view constraints from AI_VIEW_CONSTRAINTS table"""
    
    @staticmethod
    def load_constraints(view_name: str) -> Optional[Dict[str, Any]]:
        """Load constraints for a specific view/table from database"""
        try:
            conn = get_environment_snowflake_connection()
            cursor = conn.cursor()
            
            # Get constraints from database
            cursor.execute("""
                SELECT 
                    ALLOWED_OPERATIONS,
                    ALLOWED_COLUMNS,
                    FORBIDDEN_KEYWORDS,
                    BUSINESS_CONTEXT
                FROM PF.BI.AI_VIEW_CONSTRAINTS
                WHERE VIEW_NAME = %s
            """, (view_name,))
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if result:
                import json
                
                # Parse JSON fields
                allowed_ops = json.loads(result[0]) if result[0] else []
                allowed_cols = json.loads(result[1]) if result[1] else []
                forbidden = json.loads(result[2]) if result[2] else []
                context = json.loads(result[3]) if result[3] else {}
                
                return {
                    "allowed_operations": allowed_ops,
                    "allowed_columns": allowed_cols,
                    "forbidden_keywords": forbidden,
                    "business_context": context
                }
            
            # Try backward compatibility with old view name
            if view_name == "MV_CREATOR_PAYMENTS_UNION":
                return ViewConstraintsLoader.load_constraints("V_CREATOR_PAYMENTS_UNION")
                
            return None
            
        except Exception as error:
            logging.error(f"Failed to load view constraints from database: {error}")
            # Return None to trigger fallback in CortexGenerator
            return None
    
    @staticmethod
    def get_allowed_tables() -> List[str]:
        """Get list of all allowed tables from database"""
        try:
            conn = get_environment_snowflake_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT DISTINCT VIEW_NAME 
                FROM PF.BI.AI_VIEW_CONSTRAINTS
                UNION
                SELECT DISTINCT TABLE_NAME
                FROM PF.BI.AI_SCHEMA_METADATA
            """)
            
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            allowed_tables = [row[0] for row in results if row[0]]
            
            # Always include system tables
            system_tables = {
                'AI_USER_ACTIVITY_LOG',
                'AI_BUSINESS_CONTEXT',
                'AI_SCHEMA_METADATA',
                'AI_VIEW_CONSTRAINTS',
                'AI_CORTEX_PROMPTS',
                'AI_CORTEX_USAGE_LOG',
                'AI_MCP_TOOLS',
                'AI_MCP_USER_GROUPS',
                'AI_MCP_TOOL_GROUP_ACCESS'
            }
            
            return list(set(allowed_tables) | system_tables)
            
        except Exception as error:
            logging.error(f"Failed to load allowed tables from database: {error}")
            # Return minimal set for safety
            return ['MV_CREATOR_PAYMENTS_UNION', 'V_CREATOR_PAYMENTS_UNION']