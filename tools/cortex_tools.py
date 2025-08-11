"""
Cortex tools module - DEPRECATED

All Cortex-based tools are now loaded dynamically from the database.
Tool implementations have been moved to specific modules:
- query_payments_handler -> tools/payment_tools.py

This file is kept for backward compatibility only.
"""
from typing import List
from mcp.types import Tool


def get_cortex_tools() -> List[Tool]:
    """Return list of Cortex tool definitions"""
    # All tools are now loaded dynamically from database
    # No hardcoded definitions - if database is down, no tools available
    return []