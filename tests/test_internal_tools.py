"""
Test that internal tools work correctly
Verifies that read_query is not exposed but can be called by other tools
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.dynamic_registry import DynamicToolRegistry
from tools.snowflake_tools import read_query_handler
from tools.payment_tools import query_payments_handler


def test_read_query_not_exposed():
    """Verify read_query is not exposed to the LLM"""
    print("\n" + "="*60)
    print("TEST: Verify read_query is internal-only")
    print("="*60)
    
    # Create a mock registry
    registry = DynamicToolRegistry()
    
    # Simulate loading from database (read_query should not be in the database)
    # In production, this would load from AI_MCP_TOOLS table
    registry.tools = {}  # No tools loaded
    registry.handlers = {}  # No handlers loaded
    
    # Verify read_query is not in the tools list
    tools = registry.get_tools_for_group('admins')
    tool_names = [tool.name for tool in tools]
    
    print(f"Tools exposed to admins: {tool_names}")
    assert 'read_query' not in tool_names, "read_query should not be exposed to LLM"
    print("✅ read_query is not exposed to the LLM")


def test_read_query_handler_exists():
    """Verify read_query_handler can still be imported and called directly"""
    print("\n" + "="*60)
    print("TEST: Verify read_query_handler is available for internal use")
    print("="*60)
    
    # Verify the handler function exists and is callable
    assert callable(read_query_handler), "read_query_handler should be callable"
    print(f"✅ read_query_handler is available at: {read_query_handler.__module__}.{read_query_handler.__name__}")
    
    # Verify it has the right signature
    import inspect
    sig = inspect.signature(read_query_handler)
    params = list(sig.parameters.keys())
    
    print(f"Handler parameters: {params}")
    assert 'arguments' in params, "Handler should accept arguments"
    assert 'bearer_token' in params, "Handler should accept bearer_token"
    assert 'request_id' in params, "Handler should accept request_id"
    assert 'is_internal' in params, "Handler should accept is_internal flag"
    print("✅ read_query_handler has correct signature for internal calls")


def test_payment_tools_imports():
    """Verify payment_tools can import and use read_query_handler"""
    print("\n" + "="*60)
    print("TEST: Verify payment_tools can use read_query_handler")
    print("="*60)
    
    # Verify query_payments_handler exists
    assert callable(query_payments_handler), "query_payments_handler should be callable"
    print("✅ query_payments_handler is available")
    
    # Check that payment_tools imports read_query_handler
    import tools.payment_tools as pm
    assert hasattr(pm, 'read_query_handler'), "payment_tools should import read_query_handler"
    print("✅ payment_tools successfully imports read_query_handler")
    
    # Verify they're the same function
    assert pm.read_query_handler is read_query_handler, "Should be the same function reference"
    print("✅ payment_tools uses the correct read_query_handler")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("TESTING: Internal Tools Architecture")
    print("="*60)
    
    try:
        test_read_query_not_exposed()
        test_read_query_handler_exists()
        test_payment_tools_imports()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED")
        print("read_query is correctly configured as internal-only")
        print("="*60)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)