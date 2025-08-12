# Narrative Metadata Flow - Complete Mapping

**Generated:** 2025-08-12 11:45:00 PST  
**Author:** Claude Code  
**Purpose:** Document the complete flow of narrative metadata through the system

## Source: Narrative Markdown Files
**Location:** `cortex/narratives/<TABLE_NAME>.md` (e.g., `MV_CREATOR_PAYMENTS_UNION.md`)

**Parser:** `cortex/process_narrative.py`

## Where Parsed Metadata is Stored

### 1. **PF.BI.AI_SCHEMA_METADATA** Table
**What's stored:**
- `TABLE_NAME`: e.g., "MV_CREATOR_PAYMENTS_UNION" 
- `COLUMN_NAME`: Individual column names from the narrative
- `BUSINESS_MEANING`: Parsed from "meaning" field in narrative (lines 324, 330)
- `KEYWORDS`: JSON array of synonyms from narrative (line 331)
- `EXAMPLES`: Sample values from narrative (lines 308-310, 332)
- `RELATIONSHIPS`: How column relates to others (line 333)

**Populated by:** `_upsert_schema_metadata()` method (lines 298-353)

### 2. **PF.BI.AI_BUSINESS_CONTEXT** Table
**What's stored:**
- `DOMAIN`: e.g., "creator_payments" (from narrative header)
- `TITLE`: Generated as "{TABLE_NAME} Context" (line 273)
- `DESCRIPTION`: Combination of:
  - Purpose from narrative
  - Business rules list
  - Defaults list
  (lines 240-243)
- `KEYWORDS`: Aggregated synonyms from all columns (lines 245-249)
- `EXAMPLES`: Typical questions from narrative (line 252)
- `CONTEXT_TYPE`: Always "narrative" (line 287)

**Populated by:** `_upsert_business_context()` method (lines 236-296)

### 3. **PF.BI.AI_CORTEX_PROMPTS** Table (Optional)
**What's stored:**
- Custom prompt template if provided in narrative
- Only populated if `prompt_override` section exists

**Populated by:** `_upsert_cortex_prompt()` method (lines 222-223)

## Where the Metadata is Used

### 1. **Cortex SQL Generation** (`utils/prompt_builder.py`)

#### From AI_CORTEX_PROMPTS:
- **Line 125:** Loads active prompt template
- **Purpose:** Override default SQL generation template
- **Usage:** If exists, replaces DEFAULT_TEMPLATE

#### From AI_BUSINESS_CONTEXT:
- **Lines 149-169:** Loads business context for domain
- **Mapped via:** `VIEW_TO_DOMAIN_MAP` (lines 27-30)
  - "MV_CREATOR_PAYMENTS_UNION" → "creator_payments"
- **Used for:** Business rules section of Cortex prompt
- **Fallback:** Default rules if not found (line 76)

#### From AI_SCHEMA_METADATA:
- **Lines 181-202:** Loads column metadata for specific table
- **Used for:** "Relevant columns" section of prompt
- **Format:** Bullet list with meaning and examples (lines 106-113)
- **Limit:** Top 12 columns to keep prompt compact

### 2. **Dynamic Tool Loading** (`tools/dynamic_registry.py`)

#### From AI_MCP_TOOLS:
- **Lines 64-68:** Load tool definitions
- **What's used:**
  - `TOOL_DESCRIPTION`: Enhanced description (updated by `update_tool_in_db.py`)
  - `INPUT_SCHEMA`: JSON schema for tool parameters
  - `HANDLER_MODULE`: Python module to import (e.g., "tools.payment_tools")
  - `HANDLER_FUNCTION`: Function name (e.g., "query_payments_handler")

#### From AI_MCP_USER_GROUPS:
- **Lines 47-50:** Load user group definitions
- **Used for:** Access control by group path

#### From AI_MCP_TOOL_GROUP_ACCESS:
- **Lines 107-110:** Map tools to groups
- **Used for:** Determine which tools each group can access

### 3. **SQL Validation** (`validators/sql_validator_v2.py`)

#### From AI_VIEW_CONSTRAINTS via ViewConstraintsLoader:
- **Used to determine:** Which tables are allowed
- **Loaded by:** `ViewConstraintsLoader.get_allowed_tables()`
- **Combined with:** AI_SCHEMA_METADATA table names

### 4. **Constraint Loading** (`cortex/view_constraints_loader.py`)

#### From AI_VIEW_CONSTRAINTS:
- **Lines 19-45:** Load allowed operations, columns, forbidden keywords
- **Used by:** `CortexGenerator` for validation
- **Fallback:** Try old view name if MV_ not found (lines 47-48)

#### From AI_SCHEMA_METADATA:
- **Lines 65-71:** Get list of tables with metadata
- **Combined with:** AI_VIEW_CONSTRAINTS tables
- **Purpose:** Build complete allowed tables list

### 5. **Tool Description Enhancement** (`cortex/generate_tool_description.py`)

**Currently hardcoded but should use:**
- AI_BUSINESS_CONTEXT for payment types and terminology
- AI_SCHEMA_METADATA for column descriptions
- Typical questions from narrative

## Data Flow Summary

```
1. NARRATIVE FILE (MV_CREATOR_PAYMENTS_UNION.md)
   ↓ [process_narrative.py parses]
   
2. STORES IN DATABASE:
   ├─→ AI_SCHEMA_METADATA (column-level metadata)
   ├─→ AI_BUSINESS_CONTEXT (domain-level context)
   └─→ AI_CORTEX_PROMPTS (optional prompt overrides)
   
3. CONSUMED BY:
   ├─→ PromptBuilder (builds Cortex prompts)
   │   └─→ CortexGenerator (generates SQL)
   │       └─→ payment_tools.py (query_payments_handler)
   │
   ├─→ ViewConstraintsLoader (loads constraints)
   │   └─→ DynamicSqlValidator (validates SQL)
   │
   └─→ DynamicRegistry (loads tool definitions)
       └─→ MCP Server (exposes tools to LLMs)
```

## File Locations

### Scripts:
- **Parser:** `cortex/process_narrative.py`
- **Processor Command:** `python -m cortex.process_narrative cortex/narratives/MV_CREATOR_PAYMENTS_UNION.md`

### Narratives:
- **Current:** `cortex/narratives/MV_CREATOR_PAYMENTS_UNION.md`
- **Instructions:** `cortex/narratives/instructions.md`

### Consumers:
- **Prompt Builder:** `utils/prompt_builder.py`
- **Cortex Generator:** `cortex/cortex_generator_v2.py`
- **Constraint Loader:** `cortex/view_constraints_loader.py`
- **SQL Validator:** `validators/sql_validator_v2.py`
- **Dynamic Registry:** `tools/dynamic_registry.py`
- **Tool Description:** `cortex/generate_tool_description.py` (should be updated to use DB)

## Database Tables Summary

| Table | Source | Primary Consumer | Purpose |
|-------|--------|------------------|---------|
| AI_SCHEMA_METADATA | Narrative columns | PromptBuilder | Column meanings for SQL generation |
| AI_BUSINESS_CONTEXT | Narrative header/rules | PromptBuilder | Domain context for prompts |
| AI_VIEW_CONSTRAINTS | Manual/Updated | ViewConstraintsLoader | Security rules and allowed operations |
| AI_MCP_TOOLS | Manual/Script | DynamicRegistry | Tool definitions and handlers |
| AI_MCP_USER_GROUPS | Manual | DynamicRegistry | User group definitions |
| AI_MCP_TOOL_GROUP_ACCESS | Manual | DynamicRegistry | Tool-to-group mapping |
| AI_CORTEX_PROMPTS | Narrative (optional) | PromptBuilder | Custom prompt templates |