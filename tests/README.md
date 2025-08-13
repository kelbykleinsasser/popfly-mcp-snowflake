# Test Suite

## Directory Structure

- **`integration/`** - Integration tests that interact with external services
  - `test_cortex_search.py` - Tests for Cortex Search functionality
  - `test_mcp_interface.py` - Tests for MCP interface
  - `test_production_mcp.py` - Production environment tests
  - `test_synonym_results.py` - Synonym translation tests
  - etc.

- **`performance/`** - Performance and load tests
  - `test_performance.py` - Performance benchmarks

- **`manual/`** - Manual test scripts for debugging
  - `test_query.py` - Manual query testing
  - `test_tool_call.py` - Manual tool call testing

- **Unit tests** (in root of tests/)
  - `test_auth.py` - Authentication tests
  - `test_cortex_generation.py` - Cortex SQL generation tests
  - `test_sql_validation.py` - SQL validation tests
  - etc.

## Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test category
pytest tests/integration/
pytest tests/performance/

# Run specific test file
pytest tests/test_auth.py

# Run with coverage
pytest tests/ --cov=.
```