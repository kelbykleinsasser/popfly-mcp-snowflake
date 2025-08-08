# Snowflake MCP Server - HTTP Deployment

This directory contains both **local MCP server** (for Claude Desktop) and **HTTP MCP server** (for Open WebUI production deployment).

## 🏗️ Architecture

- **Local Development**: `server/mcp_server.py` - stdio MCP server for Claude Desktop
- **Production HTTP**: `server/mcp_server_http.py` - FastAPI HTTP server for Open WebUI

## 🚀 Quick Start

### Local HTTP Testing

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Set environment variables
cp .env.example .env  # Edit with your settings

# 3. Start HTTP server
python start_http_server.py

# 4. Test endpoints
curl http://localhost:8000/health
curl -H "Authorization: Bearer YOUR_API_KEY" http://localhost:8000/tools
```

### Docker Development

```bash
# Build and run with Docker Compose
docker-compose up --build

# Test health endpoint
curl http://localhost:8000/health
```

### GCP Production Deployment

```bash
# 1. Set up GCP project and secrets
gcloud config set project YOUR_PROJECT_ID

# 2. Create required secrets in Secret Manager
gcloud secrets create SNOWFLAKE_ACCOUNT --data-file=<(echo "your-account")
gcloud secrets create SNOWFLAKE_USER --data-file=<(echo "your-user")
gcloud secrets create SNOWFLAKE_ROLE --data-file=<(echo "your-role")
gcloud secrets create OPEN_WEBUI_API_KEY --data-file=<(echo "your-api-key")

# 3. Deploy using Cloud Build
gcloud builds submit --config cloudbuild.yaml
```

## 🔧 API Endpoints

### Health Check
```bash
GET /health
Response: {"status": "healthy", "snowflake_connected": true}
```

### List Available Tools
```bash
GET /tools
Headers: Authorization: Bearer YOUR_API_KEY
Response: {"success": true, "tools": [...], "count": 6}
```

### Call a Tool
```bash
POST /tools/call
Headers: Authorization: Bearer YOUR_API_KEY
Body: {"name": "query_payments", "arguments": {"query": "show recent payments"}}
Response: {"success": true, "content": [...]}
```

### Interactive Documentation
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 🔒 Authentication

The HTTP server requires **Bearer token authentication** for all tool endpoints:

```bash
# Set in .env file
OPEN_WEBUI_API_KEY=your-secure-api-key-here

# Use in requests
curl -H "Authorization: Bearer your-secure-api-key-here" http://localhost:8000/tools
```

## 🛠️ Available Tools

1. **Database Tools**:
   - `list_databases` - List available databases
   - `list_schemas` - List schemas in a database  
   - `list_tables` - List tables in a schema
   - `describe_table` - Get table schema details
   - `read_query` - Execute read-only SQL queries

2. **Natural Language Tools**:
   - `query_payments` - Query payment data using natural language (powered by Snowflake Cortex)

3. **Utility Tools**:
   - `append_insight` - Log data insights

## 🌍 Environment Configuration

### Local Development (.env)
```env
ENVIRONMENT=local
SNOWFLAKE_ACCOUNT=your-account
SNOWFLAKE_USER=your-user
SNOWFLAKE_PRIVATE_KEY_PATH=/path/to/private/key.pem
SNOWFLAKE_ROLE=your-role
OPEN_WEBUI_API_KEY=your-api-key
```

### Production (GCP Secret Manager)
```env
ENVIRONMENT=production
GCP_PROJECT_ID=your-gcp-project
# Secrets automatically loaded from GCP Secret Manager
```

## 🏥 Monitoring

### Health Check
The server includes a comprehensive health check that tests:
- Server startup and configuration
- Snowflake database connectivity
- Authentication system

### Logging
- Development: Console logging
- Production: Structured JSON logs with Cloud Logging integration
- Activity logging to Snowflake `AI_USER_ACTIVITY_LOG` table

## 🔧 Open WebUI Integration

Configure Open WebUI to connect to your deployed MCP server:

```python
# In Open WebUI configuration
MCP_SERVERS = {
    "snowflake": {
        "url": "https://your-service.run.app",
        "headers": {
            "Authorization": "Bearer your-api-key"
        }
    }
}
```

## 🐛 Troubleshooting

### Common Issues

1. **Connection Refused**: Check if server is running on correct port
2. **401 Unauthorized**: Verify `OPEN_WEBUI_API_KEY` is set correctly
3. **Snowflake Connection**: Check private key path and permissions
4. **Import Errors**: Ensure virtual environment is activated

### Debug Commands

```bash
# Check server logs
docker-compose logs -f mcp-server

# Test Snowflake connection
python -c "from utils.config import get_environment_snowflake_connection; conn = get_environment_snowflake_connection(); print('✅ Connected')"

# Validate configuration
python -c "from config.settings import settings; settings.validate_required_settings(); print('✅ Config valid')"
```

## 📊 Performance

- **Startup Time**: ~5-10 seconds (includes Snowflake connection test)
- **Memory Usage**: ~200MB base + query processing
- **Concurrency**: Supports multiple concurrent requests
- **Auto-scaling**: Configured for 1-10 Cloud Run instances