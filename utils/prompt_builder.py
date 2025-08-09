from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from utils.config import get_environment_snowflake_connection


@dataclass
class BuiltPrompt:
    prompt_text: str
    prompt_id: Optional[str]
    prompt_char_count: int
    relevant_columns_k: int


class PromptBuilder:
    """Builds DB-driven prompts for Cortex with graceful fallbacks.

    Expected tables (optional – falls back if empty):
      - PF.BI.AI_CORTEX_PROMPTS(PROMPT_ID, PROMPT_TEMPLATE, IS_ACTIVE, MODEL_NAME, TEMPERATURE, MAX_TOKENS, ...)
      - PF.BI.AI_BUSINESS_CONTEXT(DOMAIN, TITLE, DESCRIPTION, KEYWORDS, EXAMPLES, ...)
      - PF.BI.AI_SCHEMA_METADATA(TABLE_NAME, COLUMN_NAME, BUSINESS_MEANING, KEYWORDS, EXAMPLES, RELATIONSHIPS, ...)
    """

    VIEW_TO_DOMAIN_MAP: Dict[str, str] = {
        "V_CREATOR_PAYMENTS_UNION": "creator_payments",
    }

    DEFAULT_TEMPLATE = (
        "You are a Snowflake SQL expert for [[VIEW_NAME]].\n"
        "STRICT REQUIREMENTS:\n"
        "- Use only [[ALLOWED_COLUMNS]]\n"
        "- Allowed operations: [[ALLOWED_OPS]]\n"
        "- Always include LIMIT [[MAX_ROWS]]\n"
        "- No joins, CTEs, or subqueries. Use Snowflake SQL.\n\n"
        "Business context:\n[[BUSINESS_RULES]]\n\n"
        "Relevant columns (with meanings and examples):\n[[RELEVANT_COLUMN_SNIPPETS]]\n\n"
        "User query: \"[[USER_QUERY]]\"\n"
        "Return only one SQL SELECT statement."
    )

    @classmethod
    def build_prompt_for_view(
        cls,
        view_name: str,
        user_query: str,
        max_rows: int,
        allowed_ops: List[str],
        allowed_columns: List[str],
    ) -> BuiltPrompt:
        """Compose a prompt using DB rows if available, otherwise defaults."""

        # Load template (global/active)
        prompt_id, template = cls._load_active_prompt_template()

        # Load business context for the view's domain
        domain = cls.VIEW_TO_DOMAIN_MAP.get(view_name, None)
        business_rules = cls._load_business_rules(domain) if domain else None

        # Load schema metadata for relevant column snippets
        relevant_columns = cls._load_schema_metadata(view_name)
        relevant_snippets, k = cls._render_relevant_column_snippets(relevant_columns)

        if template is None:
            template = cls.DEFAULT_TEMPLATE

        # Prepare replacements
        replacement_map: Dict[str, str] = {
            "[[VIEW_NAME]]": view_name,
            "[[ALLOWED_COLUMNS]]": ", ".join(allowed_columns),
            "[[ALLOWED_OPS]]": ", ".join(allowed_ops),
            "[[MAX_ROWS]]": str(max_rows),
            "[[BUSINESS_RULES]]": business_rules or "- Creator payment tracking and analysis\n- Common filters: status, date, amount, campaign, company",
            "[[RELEVANT_COLUMN_SNIPPETS]]": relevant_snippets,
            "[[USER_QUERY]]": user_query,
        }

        prompt_text = cls._replace_placeholders(template, replacement_map).strip()

        return BuiltPrompt(
            prompt_text=prompt_text,
            prompt_id=prompt_id,
            prompt_char_count=len(prompt_text),
            relevant_columns_k=k,
        )

    # ----- Internal helpers -----

    @staticmethod
    def _replace_placeholders(template: str, mapping: Dict[str, str]) -> str:
        result = template
        for key, value in mapping.items():
            result = result.replace(key, value)
        return result

    @staticmethod
    def _render_relevant_column_snippets(rows: List[Dict[str, Optional[str]]]) -> Tuple[str, int]:
        """Render bullet list of column meanings with examples."""
        if not rows:
            return "- (No additional metadata available)", 0

        lines: List[str] = []
        for row in rows[:12]:  # cap to keep prompts compact
            column_name = (row.get("COLUMN_NAME") or "").strip()
            meaning = (row.get("BUSINESS_MEANING") or "").strip()
            examples = (row.get("EXAMPLES") or "").strip()
            # Truncate very long examples
            if len(examples) > 160:
                examples = examples[:157] + "..."
            lines.append(f"- {column_name}: {meaning} (examples: {examples})")

        return "\n".join(lines), min(len(rows), 12)

    @staticmethod
    def _load_active_prompt_template() -> Tuple[Optional[str], Optional[str]]:
        """Fetch the most recent active prompt. Returns (prompt_id, template)."""
        try:
            conn = get_environment_snowflake_connection()
            cursor = conn.cursor()
            sql = (
                "SELECT PROMPT_ID, PROMPT_TEMPLATE "
                "FROM PF.BI.AI_CORTEX_PROMPTS "
                "WHERE IS_ACTIVE = TRUE "
                "ORDER BY UPDATED_AT DESC NULLS LAST, CREATED_AT DESC NULLS LAST "
                "LIMIT 1"
            )
            cursor.execute(sql)
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            if row:
                return row[0], row[1]
        except Exception as error:
            logging.debug(f"Prompt template lookup failed (falling back): {error}")
        return None, None

    @staticmethod
    def _load_business_rules(domain: Optional[str]) -> Optional[str]:
        if not domain:
            return None
        try:
            conn = get_environment_snowflake_connection()
            cursor = conn.cursor()
            sql = (
                "SELECT TITLE, DESCRIPTION, EXAMPLES "
                "FROM PF.BI.AI_BUSINESS_CONTEXT "
                "WHERE DOMAIN = %s "
                "ORDER BY UPDATED_AT DESC NULLS LAST, CREATED_AT DESC NULLS LAST "
                "LIMIT 1"
            )
            cursor.execute(sql, (domain,))
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            if row:
                title = (row[0] or "").strip()
                description = (row[1] or "").strip()
                examples = (row[2] or "").strip()
                parts = []
                if title:
                    parts.append(f"- {title}")
                if description:
                    parts.append(f"- {description}")
                if examples:
                    parts.append(f"Examples: {examples}")
                return "\n".join(parts)
        except Exception as error:
            logging.debug(f"Business context lookup failed (falling back): {error}")
        return None

    @staticmethod
    def _load_schema_metadata(view_name: str) -> List[Dict[str, Optional[str]]]:
        try:
            conn = get_environment_snowflake_connection()
            cursor = conn.cursor()
            sql = (
                "SELECT COLUMN_NAME, BUSINESS_MEANING, EXAMPLES "
                "FROM PF.BI.AI_SCHEMA_METADATA "
                "WHERE TABLE_NAME = %s "
                "ORDER BY CREATED_AT DESC NULLS LAST"
            )
            cursor.execute(sql, (view_name,))
            rows = cursor.fetchall() or []
            # Normalize to dicts
            result: List[Dict[str, Optional[str]]] = []
            for r in rows:
                result.append(
                    {
                        "COLUMN_NAME": r[0],
                        "BUSINESS_MEANING": r[1],
                        "EXAMPLES": r[2],
                    }
                )
            cursor.close()
            conn.close()
            return result
        except Exception as error:
            logging.debug(f"Schema metadata lookup failed (falling back): {error}")
            return []


