"""
Cortex Search integration for dynamic context retrieval
Reduces prompt size from 5KB to ~500 bytes using native Snowflake search
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from utils.connection_pool import get_pooled_connection
import json
import requests
from config.settings import settings

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
                
                # Use SEARCH_PREVIEW function with proper JSON format
                query_params = json.dumps({
                    "query": query,
                    "columns": ["TABLE_NAME", "COLUMN_NAME", "BUSINESS_MEANING", "KEYWORDS", "EXAMPLES"],
                    "filter": {"@eq": {"TABLE_NAME": view_name}},
                    "limit": limit
                })
                
                search_sql = """
                SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
                    'PF.BI.SCHEMA_SEARCH',
                    %s
                )
                """
                
                cursor.execute(search_sql, (query_params,))
                result = cursor.fetchone()
                cursor.close()
                
                results = []
                if result and result[0]:
                    # Parse the JSON response
                    search_data = json.loads(result[0])
                    
                    if "results" in search_data:
                        for item in search_data["results"]:
                            results.append(SearchResult(
                                source="schema",
                                relevance_score=item.get("score", 1.0),
                                data={
                                    "table_name": item.get("TABLE_NAME"),
                                    "column_name": item.get("COLUMN_NAME"),
                                    "business_meaning": item.get("BUSINESS_MEANING"),
                                    "keywords": item.get("KEYWORDS"),
                                    "examples": item.get("EXAMPLES")
                                }
                            ))
                
                return results
                
        except Exception as e:
            logging.error(f"Schema search failed - Cortex Search service required: {e}")
            raise RuntimeError(f"Cortex Search service SCHEMA_SEARCH is required but not available: {e}")
    
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
                
                # Use SEARCH_PREVIEW function with proper JSON format
                query_params = json.dumps({
                    "query": query,
                    "columns": ["DOMAIN", "TITLE", "DESCRIPTION", "KEYWORDS", "EXAMPLES"],
                    "filter": {"@eq": {"DOMAIN": domain}},
                    "limit": limit
                })
                
                search_sql = """
                SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
                    'PF.BI.BUSINESS_CONTEXT_SEARCH',
                    %s
                )
                """
                
                cursor.execute(search_sql, (query_params,))
                result = cursor.fetchone()
                cursor.close()
                
                results = []
                if result and result[0]:
                    # Parse the JSON response
                    search_data = json.loads(result[0])
                    
                    if "results" in search_data:
                        for item in search_data["results"]:
                            results.append(SearchResult(
                                source="business",
                                relevance_score=item.get("score", 1.0),
                                data={
                                    "domain": item.get("DOMAIN"),
                                    "title": item.get("TITLE"),
                                    "description": item.get("DESCRIPTION"),
                                    "keywords": item.get("KEYWORDS"),
                                    "examples": item.get("EXAMPLES")
                                }
                            ))
                
                return results
                
        except Exception as e:
            logging.error(f"Business context search failed - Cortex Search service required: {e}")
            raise RuntimeError(f"Cortex Search service BUSINESS_CONTEXT_SEARCH is required but not available: {e}")
    
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
            logging.error(f"Constraint lookup failed: {e}")
            # Constraints are optional, so we don't raise here
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
    
