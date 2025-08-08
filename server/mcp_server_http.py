"""
HTTP-based MCP server for production deployment to GCP
Integrates with Open WebUI using FastAPI and bearer token authentication
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

from config.settings import settings
from utils.config import setup_logging
from auth_middleware.bearer_auth import validate_bearer_token
from auth_middleware.simple_auth import validate_auth
from tools.snowflake_tools import handle_snowflake_tool, get_snowflake_tools
from tools.cortex_tools import handle_cortex_tool, get_cortex_tools
from utils.logging import log_activity


class ToolCallRequest(BaseModel):
    name: str
    arguments: Dict[str, Any]


class ToolResponse(BaseModel):
    success: bool
    content: List[Dict[str, Any]]
    error: str = None


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    snowflake_connected: Optional[bool]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Validate configuration
    try:
        settings.validate_required_settings()
        logger.info("✅ Configuration validation passed")
    except Exception as error:
        logger.error(f"❌ Configuration validation failed: {error}")
        raise
    
    # Test Snowflake connection (skip in production due to IP whitelisting)
    if settings.environment != 'production':
        try:
            from utils.config import get_environment_snowflake_connection
            conn = get_environment_snowflake_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 as test")
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            logger.info(f"✅ Snowflake connection test passed: {result}")
        except Exception as error:
            logger.error(f"❌ Snowflake connection test failed: {error}")
            raise
    else:
        logger.info("⏩ Skipping Snowflake connection test in production (IP whitelisting required first)")
    
    logger.info("🚀 HTTP MCP Server initialized successfully")
    yield
    logger.info("🛑 HTTP MCP Server shutting down")


# Create FastAPI app
app = FastAPI(
    title="Snowflake MCP Server",
    description="HTTP-based MCP server for Snowflake database operations with natural language queries",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware for Open WebUI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ai.popfly.com", "https://mcp.popfly.com"],  # Restrict to known domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add middleware to log all requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests with IP information"""
    from auth_middleware.simple_auth import get_client_ip
    client_ip = get_client_ip(request)
    logging.info(f"Request from {client_ip}: {request.method} {request.url.path}")
    response = await call_next(request)
    return response


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for container orchestration"""
    # For initial deployment, don't test Snowflake connection until IP is whitelisted
    if settings.environment == 'production':
        # Production: Don't test Snowflake until network rules are configured
        snowflake_connected = None  # Unknown status
        logging.info("Production environment - Snowflake connection test skipped until IP whitelisted")
    else:
        # Local: Test actual connection
        try:
            from utils.config import get_environment_snowflake_connection
            conn = get_environment_snowflake_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            conn.close()
            snowflake_connected = True
        except Exception as e:
            logging.warning(f"Snowflake connection check failed: {str(e)}")
            snowflake_connected = False
    
    return HealthResponse(
        status="healthy",  # Always healthy for Cloud Run startup
        version="1.0.0",
        environment=settings.environment,
        snowflake_connected=snowflake_connected
    )


@app.get("/diagnostics")
async def diagnostics(token: str = Depends(validate_auth)):
    """Run diagnostics on the MCP server including logging capability"""
    diagnostics_results = {
        "environment": settings.environment,
        "snowflake_connection": False,
        "logging_capability": False,
        "recent_logs_check": False,
        "errors": []
    }
    
    try:
        # Test Snowflake connection
        from utils.config import get_environment_snowflake_connection
        conn = get_environment_snowflake_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 as test")
        cursor.fetchone()
        diagnostics_results["snowflake_connection"] = True
        
        # Test logging capability by writing a test entry
        test_insert = """
        INSERT INTO AI_USER_ACTIVITY_LOG (
            USER_EMAIL, ACTION_TYPE, ENTITY_TYPE, ENTITY_ID, 
            ACTION_DETAILS, SUCCESS, EXECUTION_TIME_MS
        )
        SELECT 
            'diagnostics@mcp.com', 'diagnostic_test', 'system', 'health_check',
            PARSE_JSON('{"test": true}'), true, 0
        """
        cursor.execute(test_insert)
        conn.commit()
        diagnostics_results["logging_capability"] = True
        
        # Check if we can read recent logs
        cursor.execute("""
            SELECT COUNT(*) as log_count 
            FROM AI_USER_ACTIVITY_LOG 
            WHERE ACTION_TIMESTAMP > DATEADD(hour, -1, CURRENT_TIMESTAMP())
        """)
        result = cursor.fetchone()
        diagnostics_results["recent_logs_check"] = True
        diagnostics_results["recent_logs_count"] = result[0] if result else 0
        
        cursor.close()
        conn.close()
        
    except Exception as error:
        diagnostics_results["errors"].append(str(error))
        logging.error(f"Diagnostics error: {error}", exc_info=True)
    
    return diagnostics_results


@app.get("/tools")
async def list_tools(request: Request, token: str = Depends(validate_auth)):
    """List all available MCP tools"""
    try:
        tools = []
        tools.extend(get_snowflake_tools())
        tools.extend(get_cortex_tools())
        
        # Convert MCP Tool objects to JSON-serializable format
        tools_list = []
        for tool in tools:
            tools_list.append({
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.inputSchema
            })
        
        await log_activity("list_tools", {}, len(tools_list), bearer_token=token)
        
        return {
            "success": True,
            "tools": tools_list,
            "count": len(tools_list)
        }
    except Exception as error:
        logging.error(f"Error listing tools: {error}")
        raise HTTPException(status_code=500, detail=f"Failed to list tools: {str(error)}")


@app.post("/tools/call", response_model=ToolResponse)
async def call_tool(
    request: ToolCallRequest,
    req: Request, 
    token: str = Depends(validate_auth)
):
    """Call a specific MCP tool with arguments"""
    try:
        tool_name = request.name
        arguments = request.arguments
        
        # Capture raw request as JSON string
        raw_request = json.dumps({
            "method": "tool_call",
            "name": tool_name,
            "arguments": arguments
        })
        
        # Log the tool call attempt
        logging.info(f"Tool call: {tool_name} with args: {arguments}")
        
        # Route to appropriate tool handler based on tool name with raw request and bearer token
        if tool_name in ['list_databases', 'list_schemas', 'list_tables', 'describe_table', 'read_query', 'append_insight']:
            result = await handle_snowflake_tool(tool_name, arguments, bearer_token=token, raw_request=raw_request)
        elif tool_name in ['query_payments']:
            result = await handle_cortex_tool(tool_name, arguments, bearer_token=token, raw_request=raw_request)
        else:
            await log_activity(tool_name, arguments, 0, execution_success=False, bearer_token=token)
            raise HTTPException(
                status_code=404, 
                detail=f"Unknown tool: {tool_name}. Available tools: list_databases, list_schemas, list_tables, describe_table, read_query, query_payments, append_insight"
            )
        
        # Convert TextContent results to JSON format
        content = []
        for item in result:
            if hasattr(item, 'text'):
                content.append({
                    "type": "text",
                    "text": item.text
                })
            elif isinstance(item, dict):
                content.append(item)
            else:
                content.append({
                    "type": "text", 
                    "text": str(item)
                })
        
        # Log successful execution
        await log_activity(tool_name, arguments, 1, execution_success=True, bearer_token=token)
        
        return ToolResponse(
            success=True,
            content=content
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 404 for unknown tools)
        raise
    except Exception as error:
        logging.error(f"Tool call failed: {tool_name} - {error}")
        
        # Log failed execution
        await log_activity(tool_name, arguments, 0, execution_success=False, bearer_token=token)
        
        return ToolResponse(
            success=False,
            content=[],
            error=str(error)
        )


@app.get("/")
async def root():
    """Root endpoint with server information"""
    return {
        "service": "Snowflake MCP Server",
        "version": "1.0.0",
        "environment": settings.environment,
        "endpoints": {
            "health": "/health",
            "tools": "/tools",
            "call_tool": "/tools/call",
            "openapi": "/openapi.json"
        },
        "authentication": "Bearer token required",
        "documentation": "/docs"
    }

@app.get("/openapi.json")
async def get_openapi():
    """Return OpenAPI specification for Open WebUI integration"""
    return app.openapi()


# Open WebUI compatible endpoints
@app.post("/v1/chat/completions")
async def openwebui_chat_completions(request: Request, token: str = Depends(validate_auth)):
    """OpenAI-compatible endpoint for Open WebUI integration"""
    return JSONResponse(
        status_code=501,
        content={
            "error": "This MCP server provides tools, not chat completions. Use /tools endpoints instead.",
            "available_endpoints": ["/tools", "/tools/call"],
            "tools_count": len(get_snowflake_tools()) + len(get_cortex_tools())
        }
    )


async def main():
    """Main entry point for production HTTP server"""
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    # Configure uvicorn for production
    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        loop="asyncio",
        log_level="info",
        access_log=True
    )
    
    server = uvicorn.Server(config)
    
    logging.info(f"🚀 Starting HTTP MCP Server on {host}:{port}")
    logging.info(f"📊 Environment: {settings.environment}")
    logging.info(f"🔒 Authentication: Bearer token required")
    logging.info(f"📖 Documentation: http://{host}:{port}/docs")
    
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())