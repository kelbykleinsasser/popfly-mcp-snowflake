"""
Cortex Search integration for dynamic context retrieval
Reduces prompt size from 5KB to ~500 bytes using native Snowflake search
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from utils.connection_pool import get_pooled_connection

@dataclass
class SearchResult:
    """Represents a Cortex Search result"""
    source: str  # schema, business, or constraint
    relevance_score: float
    data: Dict[str, Any]

class CortexSearchClient:
    """
    Client for Snowflake Cortex Search services
    Uses native search capabilities to find relevant context
    """
    
    # Search service names (as created in UI)
    SCHEMA_SEARCH = "SCHEMA_SEARCH"
    BUSINESS_SEARCH = "BUSINESS_CONTEXT_SEARCH" 
    CONSTRAINTS_SEARCH = "VIEW_CONSTRAINTS_SEARCH"
    
    # Maximum context size (characters)
    MAX_CONTEXT_SIZE = 1000
    
    @classmethod
    def search_schema_context(cls, query: str, view_name: str, limit: int = 5) -> List[SearchResult]:
        """
        Search for relevant schema columns using Cortex Search
        
        Args:
            query: Natural language query from user
            view_name: The view/table being queried
            limit: Maximum results to return
            
        Returns:
            List of search results with relevance scores
        """
        try:
            with get_pooled_connection() as conn:
                cursor = conn.cursor()
                
                # Try native Cortex Search 
                # Note: This will fail if search services aren't available
                # and fallback to keyword matching
                search_sql = """
                SELECT 
                    1.0 as relevance_score,
                    TABLE_NAME,
                    COLUMN_NAME,
                    BUSINESS_MEANING,
                    KEYWORDS,
                    EXAMPLES
                FROM AI_SCHEMA_METADATA
                WHERE SEARCH('SCHEMA_SEARCH', %s)
                AND TABLE_NAME = %s
                LIMIT %s
                """
                
                cursor.execute(search_sql, (query, view_name, limit))
                
                results = []
                for row in cursor.fetchall():
                    results.append(SearchResult(
                        source="schema",
                        relevance_score=float(row[0]),
                        data={
                            "table_name": row[1],
                            "column_name": row[2],
                            "business_meaning": row[3],
                            "keywords": row[4],
                            "examples": row[5]
                        }
                    ))
                
                cursor.close()
                return results
                
        except Exception as e:
            logging.warning(f"Schema search failed, using fallback: {e}")
            return cls._fallback_schema_search(query, view_name, limit)
    
    @classmethod
    def search_business_context(cls, query: str, domain: str = "creator_payments", limit: int = 3) -> List[SearchResult]:
        """
        Search for relevant business rules using Cortex Search
        
        Args:
            query: Natural language query from user
            domain: Business domain to search within
            limit: Maximum results to return
            
        Returns:
            List of search results with relevance scores
        """
        try:
            with get_pooled_connection() as conn:
                cursor = conn.cursor()
                
                search_sql = """
                SELECT 
                    SEARCH_SCORE() as relevance_score,
                    DOMAIN,
                    TITLE,
                    DESCRIPTION,
                    KEYWORDS,
                    EXAMPLES
                FROM TABLE(
                    SEARCHABLE_PREVIEW(
                        SERVICE_NAME => %s,
                        QUERY => %s,
                        LIMIT => %s
                    )
                )
                WHERE DOMAIN = %s
                ORDER BY relevance_score DESC
                """
                
                cursor.execute(search_sql, (cls.BUSINESS_SEARCH, query, limit, domain))
                
                results = []
                for row in cursor.fetchall():
                    results.append(SearchResult(
                        source="business",
                        relevance_score=float(row[0]),
                        data={
                            "domain": row[1],
                            "title": row[2],
                            "description": row[3],
                            "keywords": row[4],
                            "examples": row[5]
                        }
                    ))
                
                cursor.close()
                return results
                
        except Exception as e:
            logging.warning(f"Business context search failed: {e}")
            return []
    
    @classmethod
    def get_view_constraints(cls, view_name: str) -> Optional[SearchResult]:
        """
        Get constraints for a specific view
        
        Args:
            view_name: The view/table name
            
        Returns:
            Search result with view constraints or None
        """
        try:
            with get_pooled_connection() as conn:
                cursor = conn.cursor()
                
                # Direct query since we're looking for exact match
                sql = """
                SELECT 
                    1.0 as relevance_score,
                    VIEW_NAME,
                    BUSINESS_CONTEXT,
                    ALLOWED_OPERATIONS,
                    FORBIDDEN_KEYWORDS,
                    ALLOWED_COLUMNS
                FROM PF.BI.AI_VIEW_CONSTRAINTS
                WHERE VIEW_NAME = %s
                LIMIT 1
                """
                
                cursor.execute(sql, (view_name,))
                row = cursor.fetchone()
                
                if row:
                    result = SearchResult(
                        source="constraint",
                        relevance_score=1.0,
                        data={
                            "view_name": row[1],
                            "business_context": row[2],
                            "allowed_operations": row[3],
                            "forbidden_keywords": row[4],
                            "allowed_columns": row[5]
                        }
                    )
                    cursor.close()
                    return result
                
                cursor.close()
                return None
                
        except Exception as e:
            logging.warning(f"Constraint lookup failed: {e}")
            return None
    
    @classmethod
    def build_minimal_context(
        cls,
        query: str,
        view_name: str = "MV_CREATOR_PAYMENTS_UNION"
    ) -> str:
        """
        Build minimal context using Cortex Search results
        
        Args:
            query: Natural language query from user
            view_name: The view/table being queried
            
        Returns:
            Formatted minimal context string (target: 500-1000 chars)
        """
        context_parts = []
        
        # Get relevant schema columns
        schema_results = cls.search_schema_context(query, view_name, limit=8)  # Increased limit
        if schema_results:
            columns = []
            for result in schema_results[:8]:  # Top 8 most relevant
                data = result.data
                col_desc = f"{data['column_name']}: {data['business_meaning']}"
                if data.get('examples'):
                    # Truncate examples if too long
                    examples = data['examples'][:60] + "..." if len(data['examples']) > 60 else data['examples']
                    col_desc += f" (e.g., {examples})"
                columns.append(col_desc)
            
            if columns:
                context_parts.append("Relevant columns:\n" + "\n".join(f"- {c}" for c in columns))
        else:
            # If no search results, provide essential columns
            context_parts.append("""Key columns:
- PAYMENT_TYPE: Business model (Agency Mode, Direct Mode)
- PAYMENT_AMOUNT: Payment amount
- PAYMENT_DATE: Date of payment
- PAYMENT_STATUS: Status of payment""")
        
        # Get business context
        business_results = cls.search_business_context(query)
        if business_results:
            for result in business_results[:2]:  # Top 2 rules
                data = result.data
                if data.get('description'):
                    # Truncate if needed
                    desc = data['description'][:150] + "..." if len(data['description']) > 150 else data['description']
                    context_parts.append(f"Rule: {desc}")
        
        # Get view constraints
        constraints = cls.get_view_constraints(view_name)
        if constraints:
            data = constraints.data
            if data.get('allowed_operations'):
                ops = data['allowed_operations'][:100] + "..." if len(data['allowed_operations']) > 100 else data['allowed_operations']
                context_parts.append(f"Allowed operations: {ops}")
        
        # Combine and limit size
        full_context = "\n\n".join(context_parts)
        
        if len(full_context) > cls.MAX_CONTEXT_SIZE:
            full_context = full_context[:cls.MAX_CONTEXT_SIZE - 3] + "..."
        
        # Log the reduction
        original_size = 5000  # Approximate original prompt size
        new_size = len(full_context)
        reduction = (1 - new_size / original_size) * 100
        logging.info(f"Context reduced by {reduction:.1f}%: {original_size} → {new_size} chars")
        
        return full_context
    
    @classmethod
    def _fallback_schema_search(cls, query: str, view_name: str, limit: int) -> List[SearchResult]:
        """
        Fallback keyword matching when Cortex Search unavailable
        """
        try:
            with get_pooled_connection() as conn:
                cursor = conn.cursor()
                
                # Extract keywords and clean them
                keywords = [k.strip().lower() for k in query.lower().split() if len(k.strip()) > 2]
                
                if not keywords:
                    # If no keywords, return key columns
                    sql = """
                    SELECT 
                        TABLE_NAME,
                        COLUMN_NAME,
                        BUSINESS_MEANING,
                        KEYWORDS,
                        EXAMPLES
                    FROM PF.BI.AI_SCHEMA_METADATA
                    WHERE TABLE_NAME = %s
                    AND COLUMN_NAME IN ('PAYMENT_TYPE', 'PAYMENT_AMOUNT', 'PAYMENT_DATE', 'PAYMENT_STATUS')
                    LIMIT %s
                    """
                    cursor.execute(sql, (view_name, limit))
                else:
                    # Build conditions with proper parameterization
                    # Include important business-related keywords
                    important_keywords = ['payment', 'type', 'business', 'model', 'labs', 'direct', 'agency']
                    all_keywords = keywords + [k for k in important_keywords if k not in keywords]
                    
                    conditions = []
                    params = [view_name]
                    
                    for keyword in all_keywords[:10]:  # Limit to avoid too complex query
                        keyword_pattern = f'%{keyword}%'
                        conditions.append("""
                            (LOWER(COLUMN_NAME) LIKE %s OR
                             LOWER(BUSINESS_MEANING) LIKE %s OR
                             LOWER(COALESCE(KEYWORDS::VARCHAR, '')) LIKE %s)
                        """)
                        params.extend([keyword_pattern, keyword_pattern, keyword_pattern])
                    
                    where_clause = " OR ".join(conditions)
                    
                    sql = f"""
                    SELECT 
                        TABLE_NAME,
                        COLUMN_NAME,
                        BUSINESS_MEANING,
                        KEYWORDS,
                        EXAMPLES
                    FROM PF.BI.AI_SCHEMA_METADATA
                    WHERE TABLE_NAME = %s
                    AND ({where_clause})
                    LIMIT %s
                    """
                    params.append(limit)
                    cursor.execute(sql, params)
                
                results = []
                for row in cursor.fetchall():
                    results.append(SearchResult(
                        source="schema",
                        relevance_score=0.5,  # Default score for fallback
                        data={
                            "table_name": row[0],
                            "column_name": row[1],
                            "business_meaning": row[2],
                            "keywords": row[3],
                            "examples": row[4]
                        }
                    ))
                
                cursor.close()
                return results
                
        except Exception as e:
            logging.error(f"Fallback schema search failed: {e}")
            return []