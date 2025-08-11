-- Make read_query internal-only (not exposed to LLM)
-- This removes it from the AI_MCP_TOOLS table so it won't be loaded by the dynamic registry
-- but keeps the handler available for other tools to call directly

DELETE FROM PF.BI.AI_MCP_TOOLS 
WHERE TOOL_NAME = 'read_query';

-- Verify it's removed
SELECT TOOL_NAME, IS_SHARED, IS_ACTIVE 
FROM PF.BI.AI_MCP_TOOLS
ORDER BY TOOL_ID;