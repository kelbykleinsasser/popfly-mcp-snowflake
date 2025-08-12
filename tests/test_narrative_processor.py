"""
Tests for the narrative processor
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from cortex.process_narrative import NarrativeProcessor, NarrativeMetadata


class TestNarrativeProcessor:
    """Test narrative parsing and processing"""
    
    @pytest.fixture
    def sample_narrative(self, tmp_path):
        """Create a sample narrative file for testing"""
        narrative_content = """# Narrative: PF.BI.MV_TEST_TABLE

- View/Table: PF.BI.MV_TEST_TABLE (domain: test_domain)
- Purpose: Test table for unit testing

## Business rules
- Allowed operations: SELECT, WHERE, GROUP BY, ORDER BY, LIMIT
- Always include LIMIT (default 1000)
- No joins/CTEs/subqueries

## Key columns
- TEST_ID
  - Meaning: Unique test identifier
  - Synonyms: id, test_id, identifier
  - Examples: 1, 2, 3
  - Relationships: Primary key
- TEST_NAME
  - Meaning: Name of the test
  - Synonyms: name, title
  - Examples: Test1, Test2
  - Relationships: 

## Typical questions
- Show all tests
- Find test by ID
- List recent tests

## Sensitive data
- No sensitive data

## Defaults
- LIMIT 1000
- ORDER BY TEST_ID DESC
"""
        narrative_path = tmp_path / "MV_TEST_TABLE.md"
        narrative_path.write_text(narrative_content)
        return str(narrative_path)
    
    def test_parse_narrative(self, sample_narrative):
        """Test parsing a narrative file"""
        processor = NarrativeProcessor(dry_run=True)
        metadata = processor._parse_narrative(sample_narrative)
        
        assert metadata.table_name == "MV_TEST_TABLE"
        assert metadata.database == "PF"
        assert metadata.schema == "BI"
        assert metadata.domain == "test_domain"
        assert metadata.purpose == "Test table for unit testing"
        
        assert len(metadata.business_rules) == 3
        assert "Allowed operations: SELECT, WHERE, GROUP BY, ORDER BY, LIMIT" in metadata.business_rules
        
        assert len(metadata.key_columns) == 2
        assert metadata.key_columns[0]["name"] == "TEST_ID"
        assert metadata.key_columns[0]["meaning"] == "Unique test identifier"
        assert metadata.key_columns[0]["synonyms"] == ["id", "test_id", "identifier"]
        
        assert len(metadata.typical_questions) == 3
        assert "Show all tests" in metadata.typical_questions
        
        assert len(metadata.defaults) == 2
        assert "LIMIT 1000" in metadata.defaults
    
    def test_parse_narrative_with_prompt_override(self, tmp_path):
        """Test parsing with prompt override section"""
        narrative_content = """# Narrative: PF.BI.MV_TEST_TABLE

- View/Table: PF.BI.MV_TEST_TABLE (domain: test_domain)
- Purpose: Test table

## Business rules
- Test rule

## Key columns
- TEST_ID
  - Meaning: Test ID
  - Synonyms: id
  - Examples: 1
  - Relationships:

## Typical questions
- Test question

## Defaults
- LIMIT 100

## Prompt override
override: true

Custom prompt template with [[VIEW_NAME]] and [[USER_QUERY]]
"""
        narrative_path = tmp_path / "MV_TEST_WITH_PROMPT.md"
        narrative_path.write_text(narrative_content)
        
        processor = NarrativeProcessor(dry_run=True)
        metadata = processor._parse_narrative(str(narrative_path))
        
        assert metadata.prompt_override is not None
        assert "Custom prompt template" in metadata.prompt_override
        assert metadata.override_existing is True
    
    def test_parse_narrative_multiple_domains(self, tmp_path):
        """Test parsing with multiple domains"""
        narrative_content = """# Narrative: PF.BI.MV_TEST_TABLE

- View/Table: PF.BI.MV_TEST_TABLE (domain: domain1, domain2, domain3)
- Purpose: Multi-domain test

## Business rules
- Test rule

## Key columns
- TEST_ID
  - Meaning: Test
  - Synonyms: id
  - Examples: 1
  - Relationships:

## Typical questions
- Test

## Defaults
- Test
"""
        narrative_path = tmp_path / "MV_MULTI_DOMAIN.md"
        narrative_path.write_text(narrative_content)
        
        processor = NarrativeProcessor(dry_run=True)
        metadata = processor._parse_narrative(str(narrative_path))
        
        # Should take first domain as primary
        assert metadata.domain == "domain1"
    
    def test_missing_required_fields(self, tmp_path):
        """Test error handling for missing required fields"""
        # Missing domain
        narrative_content = """# Narrative: PF.BI.MV_TEST_TABLE

- View/Table: PF.BI.MV_TEST_TABLE
- Purpose: Test

## Business rules
- Test
"""
        narrative_path = tmp_path / "MV_INVALID.md"
        narrative_path.write_text(narrative_content)
        
        processor = NarrativeProcessor(dry_run=True)
        with pytest.raises(ValueError, match="Missing required domain"):
            processor._parse_narrative(str(narrative_path))
    
    @patch('cortex.process_narrative.get_environment_snowflake_connection')
    def test_validate_table(self, mock_conn):
        """Test table validation"""
        # Mock cursor and connection
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            ("TEST_ID",), 
            ("TEST_NAME",),
            ("TEST_DATE",)
        ]
        mock_conn.return_value.cursor.return_value = mock_cursor
        
        processor = NarrativeProcessor(dry_run=True)
        metadata = NarrativeMetadata(
            table_name="MV_TEST_TABLE",
            database="PF",
            schema="BI",
            domain="test",
            purpose="Test",
            business_rules=[],
            key_columns=[
                {"name": "TEST_ID"},
                {"name": "TEST_NAME"},
                {"name": "UNKNOWN_COL"}  # This should trigger warning
            ],
            typical_questions=[],
            sensitive_data=[],
            defaults=[]
        )
        
        with patch.object(processor.logger, 'warning') as mock_warning:
            actual_cols = processor._validate_table(metadata)
            
            assert actual_cols == ["TEST_ID", "TEST_NAME", "TEST_DATE"]
            mock_warning.assert_called_once()
            assert "UNKNOWN_COL" in str(mock_warning.call_args)
    
    @patch('cortex.process_narrative.get_environment_snowflake_connection')
    def test_upsert_business_context_new(self, mock_conn):
        """Test inserting new business context"""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None  # No existing record
        mock_conn.return_value.cursor.return_value = mock_cursor
        
        processor = NarrativeProcessor(dry_run=False)
        metadata = NarrativeMetadata(
            table_name="MV_TEST_TABLE",
            database="PF",
            schema="BI",
            domain="test_domain",
            purpose="Test purpose",
            business_rules=["Rule 1", "Rule 2"],
            key_columns=[
                {"name": "COL1", "synonyms": ["syn1", "syn2"]},
                {"name": "COL2", "synonyms": ["syn3"]}
            ],
            typical_questions=["Q1", "Q2"],
            sensitive_data=[],
            defaults=["Default 1"]
        )
        
        processor._upsert_business_context(mock_cursor, metadata)
        
        # Verify INSERT was called
        calls = mock_cursor.execute.call_args_list
        assert any("INSERT INTO PF.BI.AI_BUSINESS_CONTEXT" in str(call) for call in calls)
    
    @patch('cortex.process_narrative.get_environment_snowflake_connection')
    def test_upsert_business_context_update(self, mock_conn):
        """Test updating existing business context"""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (1,)  # Existing record with ID=1
        mock_conn.return_value.cursor.return_value = mock_cursor
        
        processor = NarrativeProcessor(dry_run=False)
        metadata = NarrativeMetadata(
            table_name="MV_TEST_TABLE",
            database="PF",
            schema="BI",
            domain="test_domain",
            purpose="Updated purpose",
            business_rules=["New rule"],
            key_columns=[],
            typical_questions=["New question"],
            sensitive_data=[],
            defaults=[]
        )
        
        processor._upsert_business_context(mock_cursor, metadata)
        
        # Verify UPDATE was called
        calls = mock_cursor.execute.call_args_list
        assert any("UPDATE PF.BI.AI_BUSINESS_CONTEXT" in str(call) for call in calls)
    
    @patch('cortex.process_narrative.get_environment_snowflake_connection')
    def test_dry_run_mode(self, mock_conn, sample_narrative, capsys):
        """Test dry run mode output"""
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [("TEST_ID",), ("TEST_NAME",)]
        mock_conn.return_value.cursor.return_value = mock_cursor
        
        processor = NarrativeProcessor(dry_run=True)
        processor.process_file(sample_narrative)
        
        captured = capsys.readouterr()
        assert "=== DRY RUN MODE ===" in captured.out
        assert "Table: PF.BI.MV_TEST_TABLE" in captured.out
        assert "Domain: test_domain" in captured.out
        
        # Should not write to database in dry run
        assert not any("INSERT" in str(call) for call in mock_cursor.execute.call_args_list)
        assert not any("UPDATE" in str(call) for call in mock_cursor.execute.call_args_list)
    
    def test_truncate_long_examples(self):
        """Test that long examples are truncated"""
        processor = NarrativeProcessor(dry_run=True)
        
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None  # No existing record
        
        metadata = NarrativeMetadata(
            table_name="TEST",
            database="PF",
            schema="BI",
            domain="test",
            purpose="Test",
            business_rules=[],
            key_columns=[{
                "name": "TEST_COL",
                "meaning": "Test",
                "synonyms": [],
                "examples": "x" * 250,  # Very long examples
                "relationships": ""
            }],
            typical_questions=[],
            sensitive_data=[],
            defaults=[]
        )
        
        processor._upsert_schema_metadata(mock_cursor, metadata, ["TEST_COL"])
        
        # Check that the examples were truncated
        insert_call = [call for call in mock_cursor.execute.call_args_list 
                      if "INSERT INTO PF.BI.AI_SCHEMA_METADATA" in str(call)][0]
        args = insert_call[0][1]  # Get the parameters
        examples_param = args[4]  # Examples is 5th parameter
        assert len(examples_param) <= 200
        assert examples_param.endswith("...")