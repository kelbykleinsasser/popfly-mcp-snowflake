import json
from typing import Any, Dict
from datetime import datetime

def create_success_response(message: str, data: Any = None) -> Dict[str, Any]:
    """Create standardized success response for MCP tools"""
    text = f"**Success**\n\n{message}"
    if data is not None:
        text += f"\n\n**Result:**\n```json\n{json.dumps(data, indent=2, default=str)}\n```"
    
    return {
        "content": [
            {
                "type": "text",
                "text": text
            }
        ]
    }

def create_error_response(message: str, details: Any = None) -> Dict[str, Any]:
    """Create standardized error response for MCP tools"""
    text = f"**Error**\n\n{message}"
    if details is not None:
        text += f"\n\n**Details:**\n```json\n{json.dumps(details, indent=2, default=str)}\n```"
    
    return {
        "content": [
            {
                "type": "text",
                "text": text,
                "isError": True
            }
        ]
    }