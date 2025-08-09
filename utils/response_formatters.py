"""Response formatting utilities for clean, user-friendly MCP responses"""
import json
from typing import List, Dict, Any


def format_payment_results(results: List[Dict[str, Any]], query: str) -> str:
    """Format payment query results in a clean, readable format"""
    if not results:
        return f"**No Payment Records Found**\n\nNo payment records match your query: \"{query}\"\n\nThis could mean:\n• No payments exist for the specified criteria\n• The creator name might be spelled differently\n• The payment might be pending or processed under a different reference"
    
    # Format results nicely
    formatted_results = []
    total_amount = 0
    
    for payment in results:
        payment_text = f"**{payment.get('CREATOR_NAME', 'Unknown Creator')}**"
        
        if payment.get('COMPANY_NAME'):
            payment_text += f" ({payment['COMPANY_NAME']})"
        
        amount = payment.get('PAYMENT_AMOUNT', 0)
        if isinstance(amount, str):
            try:
                amount = float(amount)
            except (ValueError, TypeError):
                amount = 0
        payment_text += f"\n• Amount: ${amount:,.2f}"
        payment_text += f"\n• Date: {payment.get('PAYMENT_DATE', 'Unknown')}"
        payment_text += f"\n• Status: {payment.get('PAYMENT_STATUS', 'Unknown')}"
        
        if payment.get('CAMPAIGN_NAME'):
            payment_text += f"\n• Campaign: {payment['CAMPAIGN_NAME']}"
            
        formatted_results.append(payment_text)
        
        # Add to total, handling string amounts
        amt = payment.get('PAYMENT_AMOUNT', 0)
        if isinstance(amt, str):
            try:
                amt = float(amt)
            except (ValueError, TypeError):
                amt = 0
        total_amount += amt
    
    result_text = f"**Found {len(results)} Payment Record{'s' if len(results) != 1 else ''}**\n\n"
    result_text += "\n\n".join(formatted_results)
    
    if len(results) > 1:
        result_text += f"\n\n**Total Amount: ${total_amount:,.2f}**"
    
    return result_text


def format_table_results(results: List[Dict[str, Any]], context: str = "") -> str:
    """Format general database query results in a clean format"""
    if not results:
        return f"**No Records Found**\n\n{context if context else 'No data matches your query criteria.'}"
    
    # For small result sets, format nicely
    if len(results) <= 10 and len(results[0].keys()) <= 6:
        formatted_results = []
        for i, row in enumerate(results, 1):
            row_text = f"**Record {i}:**"
            for key, value in row.items():
                if value is not None:
                    row_text += f"\n• {key.replace('_', ' ').title()}: {value}"
            formatted_results.append(row_text)
        
        return f"**Found {len(results)} Record{'s' if len(results) != 1 else ''}**\n\n" + "\n\n".join(formatted_results)
    
    # For larger result sets, use summary format
    else:
        sample_records = results[:3]  # Show first 3 as examples
        
        result_text = f"**Found {len(results)} Records**\n\n"
        
        # Show column names
        columns = list(results[0].keys())
        result_text += f"**Columns:** {', '.join([col.replace('_', ' ').title() for col in columns])}\n\n"
        
        # Show sample records
        result_text += "**Sample Records:**\n"
        for i, row in enumerate(sample_records, 1):
            row_values = [str(v) if v is not None else "null" for v in row.values()]
            result_text += f"{i}. {' | '.join(row_values[:4])}{'...' if len(row_values) > 4 else ''}\n"
        
        if len(results) > 3:
            result_text += f"\n... and {len(results) - 3} more records"
        
        return result_text


def format_schema_results(results: List[Dict[str, Any]], table_name: str = "") -> str:
    """Format table schema/structure results"""
    if not results:
        return f"**No Schema Information Found**\n\n{f'Table {table_name} ' if table_name else 'Table '}may not exist or you may not have permissions to view it."
    
    result_text = f"**Table Schema{f' for {table_name}' if table_name else ''}**\n\n"
    result_text += f"**{len(results)} Columns:**\n\n"
    
    for col in results:
        col_text = f"**{col.get('COLUMN_NAME', 'Unknown')}**"
        col_text += f"\n• Type: {col.get('DATA_TYPE', 'Unknown')}"
        col_text += f"\n• Nullable: {col.get('IS_NULLABLE', 'Unknown')}"
        
        if col.get('COLUMN_DEFAULT'):
            col_text += f"\n• Default: {col['COLUMN_DEFAULT']}"
            
        if col.get('COMMENT'):
            col_text += f"\n• Description: {col['COMMENT']}"
        
        result_text += col_text + "\n\n"
    
    return result_text.rstrip()


def format_list_results(results: List[Dict[str, Any]], item_type: str = "items") -> str:
    """Format simple list results (databases, schemas, tables, etc.)"""
    if not results:
        return f"**No {item_type.title()} Found**\n\nNo {item_type} are available or you may not have permissions to view them."
    
    result_text = f"**Found {len(results)} {item_type.title()}**\n\n"
    
    for item in results:
        name = item.get('name') or item.get('NAME') or 'Unknown'
        result_text += f"• **{name}**"
        
        # Add additional info if available
        if item.get('owner') or item.get('OWNER'):
            result_text += f" (Owner: {item.get('owner') or item.get('OWNER')})"
        
        if item.get('rows'):
            result_text += f" ({item['rows']} rows)"
            
        result_text += "\n"
    
    return result_text