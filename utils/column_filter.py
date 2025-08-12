"""
Intelligent column filtering to reduce Cortex prompt size
Only includes columns relevant to the user's query
"""
import re
from typing import List, Dict, Set
from config.settings import settings

class ColumnFilter:
    """Filter columns based on query relevance to reduce prompt size"""
    
    # Keywords that indicate which columns might be needed
    KEYWORD_TO_COLUMNS = {
        # Date/time related
        'today': ['PAYMENT_DATE', 'CREATED_DATE', 'INVOICE_DATE'],
        'yesterday': ['PAYMENT_DATE', 'CREATED_DATE', 'INVOICE_DATE'],
        'week': ['PAYMENT_DATE', 'CREATED_DATE', 'INVOICE_DATE'],
        'month': ['PAYMENT_DATE', 'CREATED_DATE', 'INVOICE_DATE'],
        'year': ['PAYMENT_DATE', 'CREATED_DATE', 'INVOICE_DATE'],
        'date': ['PAYMENT_DATE', 'CREATED_DATE', 'INVOICE_DATE'],
        'when': ['PAYMENT_DATE', 'CREATED_DATE', 'INVOICE_DATE'],
        'august': ['PAYMENT_DATE', 'CREATED_DATE', 'INVOICE_DATE'],
        'january': ['PAYMENT_DATE', 'CREATED_DATE', 'INVOICE_DATE'],
        'february': ['PAYMENT_DATE', 'CREATED_DATE', 'INVOICE_DATE'],
        
        # Amount/money related
        'amount': ['PAYMENT_AMOUNT', 'PLATFORM_FEE', 'STRIPE_FEE', 'CREATOR_NET'],
        'paid': ['PAYMENT_AMOUNT', 'PAYMENT_STATUS', 'PAYMENT_DATE'],
        'payment': ['PAYMENT_AMOUNT', 'PAYMENT_STATUS', 'PAYMENT_TYPE', 'PAYMENT_DATE'],
        'fee': ['PLATFORM_FEE', 'STRIPE_FEE'],
        'net': ['CREATOR_NET'],
        'total': ['PAYMENT_AMOUNT'],
        'sum': ['PAYMENT_AMOUNT'],
        'how much': ['PAYMENT_AMOUNT'],
        
        # Type/mode related
        'type': ['PAYMENT_TYPE'],
        'mode': ['PAYMENT_TYPE'],
        'agency': ['PAYMENT_TYPE'],
        'direct': ['PAYMENT_TYPE'],
        'bifurcate': ['PAYMENT_TYPE'],
        'split': ['PAYMENT_TYPE'],
        'breakdown': ['PAYMENT_TYPE'],
        
        # Entity related
        'creator': ['CREATOR_ID', 'CREATOR_NAME', 'CREATOR_EMAIL'],
        'company': ['COMPANY_ID', 'COMPANY_NAME'],
        'customer': ['COMPANY_ID', 'COMPANY_NAME'],
        'campaign': ['CAMPAIGN_ID', 'CAMPAIGN_NAME'],
        'project': ['CAMPAIGN_ID', 'CAMPAIGN_NAME'],
        'invoice': ['INVOICE_ID', 'INVOICE_NUMBER', 'INVOICE_DATE'],
        
        # Status related
        'status': ['PAYMENT_STATUS'],
        'pending': ['PAYMENT_STATUS'],
        'failed': ['PAYMENT_STATUS'],
        'open': ['PAYMENT_STATUS'],
        
        # Count/list related
        'count': ['PAYMENT_ID'],
        'how many': ['PAYMENT_ID'],
        'list': ['PAYMENT_ID'],
        'show': ['PAYMENT_ID'],
        'recent': ['PAYMENT_DATE', 'CREATED_DATE'],
        'latest': ['PAYMENT_DATE', 'CREATED_DATE'],
        'last': ['PAYMENT_DATE', 'CREATED_DATE'],
        
        # Grouping hints
        'by': [],  # Will include whatever comes after "by"
        'per': [],  # Will include whatever comes after "per"
        'each': [],  # Will include whatever comes after "each"
    }
    
    # Always include these core columns
    ALWAYS_INCLUDE = {
        'PAYMENT_ID',  # Primary key
        'PAYMENT_TYPE',  # Often needed for filtering
        'PAYMENT_STATUS',  # Often needed for filtering
    }
    
    @classmethod
    def filter_columns(cls, user_query: str, all_columns: List[str]) -> List[str]:
        """
        Filter columns based on query relevance
        
        Args:
            user_query: The natural language query from the user
            all_columns: All available columns in the table
            
        Returns:
            List of columns relevant to the query
        """
        # If intelligent filtering is disabled, return all columns
        if not settings.cortex_intelligent_filtering:
            return all_columns
        
        query_lower = user_query.lower()
        relevant_columns = set(cls.ALWAYS_INCLUDE)
        
        # Check each keyword
        for keyword, columns in cls.KEYWORD_TO_COLUMNS.items():
            if keyword in query_lower:
                relevant_columns.update(columns)
        
        # Special handling for "group by", "order by", etc.
        group_patterns = [
            r'group\s+by\s+(\w+)',
            r'by\s+(\w+)',
            r'per\s+(\w+)',
            r'for\s+each\s+(\w+)',
        ]
        
        for pattern in group_patterns:
            matches = re.findall(pattern, query_lower)
            for match in matches:
                # Try to find columns that match this term
                for col in all_columns:
                    if match in col.lower():
                        relevant_columns.add(col)
        
        # If we're doing aggregations, make sure we have the right columns
        if any(word in query_lower for word in ['sum', 'total', 'count', 'average', 'avg', 'max', 'min']):
            relevant_columns.add('PAYMENT_AMOUNT')
        
        # If very few columns selected, include a few more common ones for safety
        if len(relevant_columns) < 5:
            relevant_columns.update(['PAYMENT_DATE', 'PAYMENT_AMOUNT', 'CREATOR_NAME', 'COMPANY_NAME'])
        
        # Return only columns that actually exist in the table
        return [col for col in all_columns if col in relevant_columns]
    
    @classmethod
    def get_filter_status(cls) -> str:
        """Get a string describing the current filter status"""
        if settings.cortex_intelligent_filtering:
            return "ENABLED - Only sending relevant columns to Cortex"
        else:
            return "DISABLED - Sending all columns to Cortex"