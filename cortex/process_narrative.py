#!/usr/bin/env python3
"""
Process narrative markdown files to populate Snowflake metadata tables.

This script parses cortex/narratives/<VIEW_NAME>.md files and populates:
- PF.BI.AI_SCHEMA_METADATA (column semantics)
- PF.BI.AI_BUSINESS_CONTEXT (domain context + examples)
- PF.BI.AI_CORTEX_PROMPTS (optional prompt override)

Usage:
    python -m cortex.process_narrative cortex/narratives/MV_CREATOR_PAYMENTS_UNION.md
"""

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from utils.config import get_environment_snowflake_connection
from config.settings import settings


@dataclass
class NarrativeMetadata:
    """Parsed narrative metadata"""
    table_name: str
    database: str
    schema: str
    domain: str
    purpose: str
    business_rules: List[str]
    key_columns: List[Dict[str, Any]]
    typical_questions: List[str]
    sensitive_data: List[str]
    defaults: List[str]
    prompt_override: Optional[str] = None
    override_existing: bool = False


class NarrativeProcessor:
    """Process narrative markdown files into database metadata"""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.logger = logging.getLogger(__name__)
        
    def process_file(self, filepath: str) -> bool:
        """Process a single narrative file"""
        try:
            self.logger.info(f"Processing narrative: {filepath}")
            
            # Parse the markdown file
            metadata = self._parse_narrative(filepath)
            
            # Validate the table exists and get columns
            actual_columns = self._validate_table(metadata)
            
            # Process into database (or dry run)
            if self.dry_run:
                self._print_dry_run(metadata, actual_columns)
            else:
                self._write_to_database(metadata, actual_columns)
            
            self.logger.info(f"Successfully processed {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to process {filepath}: {e}")
            return False
    
    def _parse_narrative(self, filepath: str) -> NarrativeMetadata:
        """Parse markdown narrative file"""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Narrative file not found: {filepath}")
        
        content = path.read_text()
        lines = content.split('\n')
        
        # Initialize collectors
        metadata = NarrativeMetadata(
            table_name="",
            database=settings.snowflake_database,
            schema=settings.snowflake_schema,
            domain="",
            purpose="",
            business_rules=[],
            key_columns=[],
            typical_questions=[],
            sensitive_data=[],
            defaults=[]
        )
        
        # Parse top matter
        for line in lines[:10]:
            if "View/Table:" in line:
                match = re.search(r'([A-Z_]+)\.([A-Z_]+)\.([A-Z_]+)\s*\(domain:\s*([^)]+)\)', line)
                if match:
                    metadata.database = match.group(1)
                    metadata.schema = match.group(2)
                    metadata.table_name = match.group(3)
                    # Handle multiple domains - take first as primary
                    domains = match.group(4).split(',')
                    metadata.domain = domains[0].strip()
            elif "Purpose:" in line:
                metadata.purpose = line.split("Purpose:", 1)[1].strip()
        
        # Parse sections
        current_section = None
        current_column = None
        
        for line in lines:
            line_stripped = line.strip()
            
            # Check for section headers
            if line_stripped.startswith("## "):
                current_section = line_stripped[3:].lower()
                current_column = None
                continue
            
            # Process based on current section
            if current_section == "business rules":
                if line_stripped.startswith("- "):
                    metadata.business_rules.append(line_stripped[2:])
                    
            elif current_section == "key columns":
                if line_stripped.startswith("- ") and not any(line_stripped.startswith(f"- {k}:") for k in ["Meaning", "Synonyms", "Examples", "Relationships"]):
                    # New column
                    column_name = line_stripped[2:].strip()
                    current_column = {
                        "name": column_name,
                        "meaning": "",
                        "synonyms": [],
                        "examples": "",
                        "relationships": ""
                    }
                    metadata.key_columns.append(current_column)
                elif current_column and line_stripped.startswith("- Meaning:"):
                    current_column["meaning"] = line_stripped.split(":", 1)[1].strip()
                elif current_column and line_stripped.startswith("- Synonyms:"):
                    synonyms_text = line_stripped.split(":", 1)[1].strip()
                    current_column["synonyms"] = [s.strip() for s in synonyms_text.split(",")]
                elif current_column and line_stripped.startswith("- Examples:"):
                    current_column["examples"] = line_stripped.split(":", 1)[1].strip()
                elif current_column and line_stripped.startswith("- Relationships:"):
                    current_column["relationships"] = line_stripped.split(":", 1)[1].strip()
                    
            elif current_section == "typical questions":
                if line_stripped.startswith("- "):
                    metadata.typical_questions.append(line_stripped[2:])
                    
            elif current_section == "sensitive data":
                if line_stripped.startswith("- "):
                    metadata.sensitive_data.append(line_stripped[2:])
                    
            elif current_section == "defaults":
                if line_stripped.startswith("- "):
                    metadata.defaults.append(line_stripped[2:])
                    
            elif current_section == "prompt override":
                if line_stripped.startswith("override:"):
                    metadata.override_existing = "true" in line_stripped.lower()
                elif line_stripped and not line_stripped.startswith("#"):
                    if metadata.prompt_override is None:
                        metadata.prompt_override = ""
                    metadata.prompt_override += line + "\n"
        
        # Validate required fields
        if not metadata.table_name:
            raise ValueError("Missing required View/Table specification")
        if not metadata.domain:
            raise ValueError("Missing required domain specification")
        
        return metadata
    
    def _validate_table(self, metadata: NarrativeMetadata) -> List[str]:
        """Validate table exists and return actual columns"""
        conn = get_environment_snowflake_connection()
        cursor = conn.cursor()
        
        try:
            # Check if table/view exists
            fq_name = f"{metadata.database}.{metadata.schema}.{metadata.table_name}"
            cursor.execute(f"DESCRIBE TABLE {fq_name}")
            
            actual_columns = []
            for row in cursor.fetchall():
                actual_columns.append(row[0])  # Column name is first field
            
            # Warn about columns in narrative not in table
            narrative_columns = {col["name"] for col in metadata.key_columns}
            unknown_columns = narrative_columns - set(actual_columns)
            if unknown_columns:
                self.logger.warning(f"Columns in narrative not found in table: {unknown_columns}")
            
            return actual_columns
            
        finally:
            cursor.close()
            conn.close()
    
    def _write_to_database(self, metadata: NarrativeMetadata, actual_columns: List[str]) -> None:
        """Write metadata to database tables"""
        conn = get_environment_snowflake_connection()
        cursor = conn.cursor()
        
        try:
            # Start transaction
            cursor.execute("BEGIN")
            
            # 1. Upsert AI_BUSINESS_CONTEXT
            self._upsert_business_context(cursor, metadata)
            
            # 2. Upsert AI_SCHEMA_METADATA for each column
            self._upsert_schema_metadata(cursor, metadata, actual_columns)
            
            # 3. Optional: Upsert AI_CORTEX_PROMPTS
            if metadata.prompt_override:
                self._upsert_cortex_prompt(cursor, metadata)
            
            # Commit transaction
            cursor.execute("COMMIT")
            self.logger.info("Successfully wrote metadata to database")
            
        except Exception as e:
            cursor.execute("ROLLBACK")
            raise e
        finally:
            cursor.close()
            conn.close()
    
    def _upsert_business_context(self, cursor, metadata: NarrativeMetadata) -> None:
        """Upsert business context for domain"""
        
        # Build description from rules and defaults
        description_parts = [metadata.purpose]
        description_parts.extend(metadata.business_rules)
        description_parts.extend(metadata.defaults)
        description = "\n".join(description_parts)
        
        # Collect all keywords from columns
        all_keywords = []
        for col in metadata.key_columns:
            all_keywords.extend(col.get("synonyms", []))
        unique_keywords = list(set(all_keywords))
        
        # Build examples
        examples = "\n".join(metadata.typical_questions)
        
        # Check if domain exists
        cursor.execute("""
            SELECT ID FROM PF.BI.AI_BUSINESS_CONTEXT 
            WHERE DOMAIN = %s
        """, (metadata.domain,))
        
        existing = cursor.fetchone()
        
        if existing:
            # Update existing
            cursor.execute("""
                UPDATE PF.BI.AI_BUSINESS_CONTEXT
                SET TITLE = %s,
                    DESCRIPTION = %s,
                    KEYWORDS = %s::VARIANT,
                    EXAMPLES = %s,
                    UPDATED_AT = CURRENT_TIMESTAMP()
                WHERE DOMAIN = %s
            """, (
                f"{metadata.table_name} Context",
                description,
                json.dumps(unique_keywords),  # Convert array to JSON string for VARIANT
                examples,
                metadata.domain
            ))
            self.logger.info(f"Updated business context for domain: {metadata.domain}")
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO PF.BI.AI_BUSINESS_CONTEXT 
                (ID, DOMAIN, TITLE, DESCRIPTION, KEYWORDS, EXAMPLES, CONTEXT_TYPE, CREATED_AT, UPDATED_AT)
                SELECT 
                    COALESCE(MAX(ID), 0) + 1,
                    %s, %s, %s, %s::VARIANT, %s, 'narrative', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP()
                FROM PF.BI.AI_BUSINESS_CONTEXT
            """, (
                metadata.domain,
                f"{metadata.table_name} Context",
                description,
                json.dumps(unique_keywords),  # Convert array to JSON string for VARIANT
                examples
            ))
            self.logger.info(f"Inserted business context for domain: {metadata.domain}")
    
    def _upsert_schema_metadata(self, cursor, metadata: NarrativeMetadata, actual_columns: List[str]) -> None:
        """Upsert schema metadata for columns"""
        
        for col in metadata.key_columns:
            # Skip if column not in actual table
            if col["name"] not in actual_columns:
                self.logger.warning(f"Skipping column not in table: {col['name']}")
                continue
            
            # Truncate examples if too long
            examples = col.get("examples", "")
            if len(examples) > 200:
                examples = examples[:197] + "..."
            
            # Check if column metadata exists
            cursor.execute("""
                SELECT ID FROM PF.BI.AI_SCHEMA_METADATA
                WHERE TABLE_NAME = %s AND COLUMN_NAME = %s
            """, (metadata.table_name, col["name"]))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update existing
                cursor.execute("""
                    UPDATE PF.BI.AI_SCHEMA_METADATA
                    SET BUSINESS_MEANING = %s,
                        KEYWORDS = %s::VARIANT,
                        EXAMPLES = %s,
                        RELATIONSHIPS = %s
                    WHERE TABLE_NAME = %s AND COLUMN_NAME = %s
                """, (
                    col.get("meaning", ""),
                    json.dumps(col.get("synonyms", [])),  # Convert array to JSON string
                    examples,
                    col.get("relationships", ""),
                    metadata.table_name,
                    col["name"]
                ))
                self.logger.info(f"Updated metadata for column: {col['name']}")
            else:
                # Insert new
                cursor.execute("""
                    INSERT INTO PF.BI.AI_SCHEMA_METADATA
                    (ID, TABLE_NAME, COLUMN_NAME, BUSINESS_MEANING, KEYWORDS, EXAMPLES, RELATIONSHIPS, CREATED_AT)
                    SELECT
                        COALESCE(MAX(ID), 0) + 1,
                        %s, %s, %s, %s::VARIANT, %s, %s, CURRENT_TIMESTAMP()
                    FROM PF.BI.AI_SCHEMA_METADATA
                """, (
                    metadata.table_name,
                    col["name"],
                    col.get("meaning", ""),
                    json.dumps(col.get("synonyms", [])),  # Convert array to JSON string
                    examples,
                    col.get("relationships", "")
                ))
                self.logger.info(f"Inserted metadata for column: {col['name']}")
    
    def _upsert_cortex_prompt(self, cursor, metadata: NarrativeMetadata) -> None:
        """Upsert Cortex prompt if override specified"""
        
        # Check for existing active prompt
        cursor.execute("""
            SELECT PROMPT_ID FROM PF.BI.AI_CORTEX_PROMPTS
            WHERE IS_ACTIVE = TRUE
            ORDER BY UPDATED_AT DESC NULLS LAST, CREATED_AT DESC NULLS LAST
            LIMIT 1
        """)
        
        existing = cursor.fetchone()
        
        if existing and not metadata.override_existing:
            self.logger.info("Active prompt exists and override not specified, skipping prompt update")
            return
        
        # Deactivate existing prompts if overriding
        if metadata.override_existing:
            cursor.execute("""
                UPDATE PF.BI.AI_CORTEX_PROMPTS
                SET IS_ACTIVE = FALSE,
                    UPDATED_AT = CURRENT_TIMESTAMP()
                WHERE IS_ACTIVE = TRUE
            """)
        
        # Insert new prompt
        import uuid
        prompt_id = str(uuid.uuid4())
        
        cursor.execute("""
            INSERT INTO PF.BI.AI_CORTEX_PROMPTS
            (PROMPT_ID, PROMPT_TEMPLATE, MODEL_NAME, TEMPERATURE, MAX_TOKENS, IS_ACTIVE, CREATED_AT, UPDATED_AT)
            VALUES (%s, %s, %s, %s, %s, TRUE, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP())
        """, (
            prompt_id,
            metadata.prompt_override,
            settings.cortex_model,
            0.1,
            1200
        ))
        
        self.logger.info(f"Inserted new Cortex prompt: {prompt_id}")
    
    def _print_dry_run(self, metadata: NarrativeMetadata, actual_columns: List[str]) -> None:
        """Print what would be written in dry run mode"""
        print("\n=== DRY RUN MODE ===\n")
        
        print(f"Table: {metadata.database}.{metadata.schema}.{metadata.table_name}")
        print(f"Domain: {metadata.domain}")
        print(f"Purpose: {metadata.purpose}")
        
        print(f"\nBusiness Rules ({len(metadata.business_rules)}):")
        for rule in metadata.business_rules[:3]:
            print(f"  - {rule}")
        if len(metadata.business_rules) > 3:
            print(f"  ... and {len(metadata.business_rules) - 3} more")
        
        print(f"\nKey Columns ({len(metadata.key_columns)}):")
        for col in metadata.key_columns[:5]:
            print(f"  - {col['name']}: {col.get('meaning', 'No meaning provided')}")
        if len(metadata.key_columns) > 5:
            print(f"  ... and {len(metadata.key_columns) - 5} more")
        
        print(f"\nTypical Questions ({len(metadata.typical_questions)}):")
        for q in metadata.typical_questions[:3]:
            print(f"  - {q}")
        
        print(f"\nDefaults ({len(metadata.defaults)}):")
        for d in metadata.defaults:
            print(f"  - {d}")
        
        if metadata.prompt_override:
            print(f"\nPrompt Override: Yes (override_existing={metadata.override_existing})")
            print(f"  First 200 chars: {metadata.prompt_override[:200]}...")
        
        # Check columns
        narrative_columns = {col["name"] for col in metadata.key_columns}
        unknown_columns = narrative_columns - set(actual_columns)
        if unknown_columns:
            print(f"\n⚠️  WARNING: Columns in narrative not found in table: {unknown_columns}")
        
        print("\n=== END DRY RUN ===\n")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Process narrative markdown files")
    parser.add_argument("narrative_file", help="Path to narrative markdown file")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without writing to database")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Process the file
    processor = NarrativeProcessor(dry_run=args.dry_run)
    success = processor.process_file(args.narrative_file)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()