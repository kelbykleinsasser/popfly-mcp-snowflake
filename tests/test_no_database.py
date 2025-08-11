"""
Test to verify system behavior when database is unavailable
Confirms that no hardcoded tool definitions exist
"""
import sys
from unittest.mock import patch, MagicMock


def test_no_hardcoded_tools():
    """Verify static tool functions return empty lists"""
    from tools.snowflake_tools import get_snowflake_tools
    from tools.cortex_tools import get_cortex_tools
    
    snowflake_tools = get_snowflake_tools()
    cortex_tools = get_cortex_tools()
    
    print("Testing static tool functions:")
    print(f"  get_snowflake_tools(): {snowflake_tools}")
    print(f"  get_cortex_tools(): {cortex_tools}")
    
    assert snowflake_tools == [], f"Expected empty list, got {snowflake_tools}"
    assert cortex_tools == [], f"Expected empty list, got {cortex_tools}"
    print("✅ No hardcoded tool definitions found\n")


def test_registry_with_database_failure():
    """Test registry behavior when database connection fails"""
    
    # Mock the database connection to simulate failure
    with patch('tools.dynamic_registry.get_environment_snowflake_connection') as mock_conn:
        mock_conn.side_effect = Exception("Database connection failed (simulated)")
        
        from tools.dynamic_registry import DynamicToolRegistry
        
        registry = DynamicToolRegistry()
        
        try:
            registry.load_from_database()
            print("❌ Registry loaded unexpectedly")
            assert False, "Registry should have failed to load"
        except Exception as e:
            print(f"✅ Registry failed as expected: {str(e)[:80]}...")
            
            # Verify no tools or handlers were loaded
            assert len(registry.tools) == 0, f"Expected 0 tools, got {len(registry.tools)}"
            assert len(registry.handlers) == 0, f"Expected 0 handlers, got {len(registry.handlers)}"
            assert len(registry.groups) == 0, f"Expected 0 groups, got {len(registry.groups)}"
            
            print(f"  Tools loaded: {len(registry.tools)}")
            print(f"  Handlers loaded: {len(registry.handlers)}")
            print(f"  Groups loaded: {len(registry.groups)}")
            print("✅ Registry correctly has no tools when database is down\n")


def test_list_tools_with_no_registry():
    """Test what list_tools returns when registry has no tools"""
    from tools.dynamic_registry import DynamicToolRegistry
    
    # Create empty registry (simulating failed database load)
    registry = DynamicToolRegistry()
    
    # Get tools for default group
    tools = registry.get_tools_for_group('default')
    
    print("Testing list_tools with empty registry:")
    print(f"  Tools returned: {tools}")
    assert tools == [], f"Expected empty list, got {tools}"
    print("✅ list_tools correctly returns empty list when no tools loaded\n")


if __name__ == "__main__":
    print("="*60)
    print("TESTING: No Hardcoded Tools & Database Failure Handling")
    print("="*60 + "\n")
    
    test_no_hardcoded_tools()
    test_registry_with_database_failure()
    test_list_tools_with_no_registry()
    
    print("="*60)
    print("✅ ALL TESTS PASSED - System is fully database-driven")
    print("="*60)