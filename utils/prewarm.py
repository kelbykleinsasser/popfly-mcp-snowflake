"""
Connection and Cortex pre-warming to avoid cold starts
"""
import logging
import asyncio
from config.settings import settings
from utils.connection_pool import get_pooled_connection

async def prewarm_connections():
    """Pre-warm Snowflake connections and Cortex to avoid cold starts"""
    
    if not settings.cortex_prewarm_on_startup:
        logging.info("Connection pre-warming is disabled")
        return
    
    logging.info("Pre-warming connections and Cortex...")
    
    try:
        # Pre-warm connection pool
        with get_pooled_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            logging.info("✓ Connection pool pre-warmed")
        
        # Pre-warm Cortex with a simple query
        from cortex.cortex_generator_v2 import CortexGenerator
        
        simple_prompt = """
        You are a SQL expert. Generate SQL for: "Select 1"
        Return only: SELECT 1
        """
        
        result = await CortexGenerator.call_cortex_complete(simple_prompt)
        logging.info(f"✓ Cortex pre-warmed (response: {result[:50]}...)")
        
        # Pre-warm database metadata loading
        from cortex.view_constraints_loader import ViewConstraintsLoader
        ViewConstraintsLoader.get_allowed_tables()
        logging.info("✓ Metadata cache pre-warmed")
        
        logging.info("Pre-warming complete!")
        
    except Exception as e:
        logging.warning(f"Pre-warming failed (non-critical): {e}")
        # Don't fail startup if pre-warming fails