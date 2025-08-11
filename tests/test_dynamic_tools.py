"""
Test suite for dynamic tool system
Validates database-handler consistency and group-based access
"""
import asyncio
import json
import logging
from typing import Dict, Any
from tools.dynamic_registry import DynamicToolRegistry
from utils.config import get_environment_snowflake_connection


class DynamicToolTests:
    """Test suite for dynamic tool system"""
    
    def __init__(self):
        self.registry = DynamicToolRegistry()
        self.results = []
        
    def test_database_connection(self) -> bool:
        """Test basic database connectivity"""
        try:
            conn = get_environment_snowflake_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM PF.BI.AI_MCP_TOOLS")
            count = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            self.results.append(f"✅ Database connection successful. Found {count} tools.")
            return True
        except Exception as e:
            self.results.append(f"❌ Database connection failed: {e}")
            return False
    
    def test_registry_loading(self) -> bool:
        """Test loading tools from database into registry"""
        try:
            self.registry.load_from_database()
            
            tool_count = len(self.registry.tools)
            group_count = len(self.registry.groups)
            handler_count = len(self.registry.handlers)
            
            self.results.append(f"✅ Registry loaded: {tool_count} tools, {group_count} groups, {handler_count} handlers")
            
            # Verify specific tools exist
            if 'query_payments' in self.registry.tools:
                self.results.append("✅ query_payments tool loaded")
            else:
                self.results.append("❌ query_payments tool not found")
                return False
                
            if 'read_query' in self.registry.tools:
                self.results.append("✅ read_query tool loaded")
            else:
                self.results.append("❌ read_query tool not found")
                return False
            
            return True
        except Exception as e:
            self.results.append(f"❌ Registry loading failed: {e}")
            return False
    
    def test_handler_validation(self) -> bool:
        """Verify all database tools have valid handlers"""
        try:
            success = True
            for tool_name, tool in self.registry.tools.items():
                handler = self.registry.handlers.get(tool_name)
                if handler and callable(handler):
                    self.results.append(f"✅ {tool_name}: Handler valid ({tool.handler_module}.{tool.handler_function})")
                else:
                    self.results.append(f"❌ {tool_name}: Handler missing or not callable")
                    success = False
            
            return success
        except Exception as e:
            self.results.append(f"❌ Handler validation failed: {e}")
            return False
    
    def test_group_access(self) -> bool:
        """Test group-based tool access"""
        try:
            # Test default group
            default_tools = self.registry.get_tools_for_group('default')
            default_names = [t.name for t in default_tools]
            
            # Test admin group
            admin_tools = self.registry.get_tools_for_group('admins')
            admin_names = [t.name for t in admin_tools]
            
            # Test account managers group
            am_tools = self.registry.get_tools_for_group('accountmanagers')
            am_names = [t.name for t in am_tools]
            
            self.results.append(f"✅ Default group has {len(default_names)} tools: {default_names}")
            self.results.append(f"✅ Admin group has {len(admin_names)} tools: {admin_names}")
            self.results.append(f"✅ Account Managers have {len(am_names)} tools: {am_names}")
            
            # Verify shared tools appear in all groups
            if 'read_query' in default_names and 'read_query' in admin_names and 'read_query' in am_names:
                self.results.append("✅ Shared tool 'read_query' available to all groups")
            else:
                self.results.append("❌ Shared tool 'read_query' not available to all groups")
                return False
            
            # Verify group-specific tools
            if 'query_payments' in admin_names and 'query_payments' in am_names:
                self.results.append("✅ 'query_payments' available to authorized groups")
            else:
                self.results.append("❌ 'query_payments' not available to authorized groups")
                return False
                
            if 'query_payments' not in default_names:
                self.results.append("✅ 'query_payments' correctly restricted from default group")
            else:
                self.results.append("❌ 'query_payments' incorrectly available to default group")
                return False
            
            return True
        except Exception as e:
            self.results.append(f"❌ Group access test failed: {e}")
            return False
    
    def test_input_schema_validation(self) -> bool:
        """Verify input schemas are valid JSON Schema"""
        try:
            success = True
            for tool_name, tool in self.registry.tools.items():
                if isinstance(tool.input_schema, dict):
                    # Check required JSON Schema fields
                    if 'type' in tool.input_schema:
                        self.results.append(f"✅ {tool_name}: Valid input schema")
                    else:
                        self.results.append(f"❌ {tool_name}: Invalid schema - missing 'type' field")
                        success = False
                else:
                    self.results.append(f"❌ {tool_name}: Input schema is not a dictionary")
                    success = False
            
            return success
        except Exception as e:
            self.results.append(f"❌ Schema validation failed: {e}")
            return False
    
    async def test_tool_execution(self) -> bool:
        """Test actual tool execution with the dynamic system"""
        try:
            # Test read_query tool
            read_query_args = {
                "query": "SELECT 1 as test_value",
                "max_rows": 1
            }
            
            result = await self.registry.handle_tool_call(
                "read_query",
                read_query_args,
                group_path="default"
            )
            
            if result and result[0].text:
                self.results.append("✅ read_query execution successful")
            else:
                self.results.append("❌ read_query execution failed - no result")
                return False
            
            # Test query_payments tool (for admin group)
            query_payments_args = {
                "query": "Show me the latest payment",
                "max_rows": 1
            }
            
            result = await self.registry.handle_tool_call(
                "query_payments",
                query_payments_args,
                group_path="admins"
            )
            
            if result and result[0].text:
                self.results.append("✅ query_payments execution successful")
            else:
                self.results.append("❌ query_payments execution failed - no result")
                return False
            
            # Test unauthorized access
            result = await self.registry.handle_tool_call(
                "query_payments",
                query_payments_args,
                group_path="default"
            )
            
            if "not available" in result[0].text.lower():
                self.results.append("✅ Unauthorized access correctly blocked")
            else:
                self.results.append("❌ Unauthorized access not blocked")
                return False
            
            return True
            
        except Exception as e:
            self.results.append(f"❌ Tool execution test failed: {e}")
            return False
    
    def run_all_tests(self):
        """Run all tests and print results"""
        print("\n" + "="*60)
        print("DYNAMIC TOOL SYSTEM TEST SUITE")
        print("="*60 + "\n")
        
        tests = [
            ("Database Connection", self.test_database_connection),
            ("Registry Loading", self.test_registry_loading),
            ("Handler Validation", self.test_handler_validation),
            ("Group Access Control", self.test_group_access),
            ("Input Schema Validation", self.test_input_schema_validation),
        ]
        
        all_passed = True
        for test_name, test_func in tests:
            print(f"\n{test_name}:")
            print("-" * 40)
            passed = test_func()
            if not passed:
                all_passed = False
        
        # Run async test
        print(f"\nTool Execution:")
        print("-" * 40)
        loop = asyncio.get_event_loop()
        passed = loop.run_until_complete(self.test_tool_execution())
        if not passed:
            all_passed = False
        
        # Print all results
        print("\n" + "="*60)
        print("TEST RESULTS:")
        print("="*60)
        for result in self.results:
            print(result)
        
        print("\n" + "="*60)
        if all_passed:
            print("✅ ALL TESTS PASSED")
        else:
            print("❌ SOME TESTS FAILED")
        print("="*60 + "\n")
        
        return all_passed


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Run tests
    tester = DynamicToolTests()
    success = tester.run_all_tests()
    
    # Exit with appropriate code
    exit(0 if success else 1)