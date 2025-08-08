#!/usr/bin/env python3
"""
Simple script to start the HTTP MCP server for local testing
"""
import os
import sys
import asyncio

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.mcp_server_http import main

if __name__ == "__main__":
    print("🚀 Starting Snowflake MCP HTTP Server...")
    print("📖 Documentation: http://localhost:8000/docs")
    print("🔍 Health check: http://localhost:8000/health")
    print("🛠️  Tools endpoint: http://localhost:8000/tools")
    print("⚡ Use Ctrl+C to stop")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Server error: {e}")
        sys.exit(1)