# Open WebUI Integration Guide

## Overview
This guide describes how to configure Open WebUI to connect to the Popfly MCP Snowflake server with group-based access control.

## Quick Setup

### Group-Based URLs

Different user groups access different tool sets through specific URL paths:

| User Group | URL | Available Tools |
|------------|-----|-----------------|
| Default Users | `https://mcp.popfly.com/tools` | No tools currently (expandable via database) |
| Admins | `https://mcp.popfly.com/admins/tools` | query_payments |
| Account Managers | `https://mcp.popfly.com/accountmanagers/tools` | query_payments |

### 1. In Open WebUI Admin Panel
Navigate to **Admin Panel** → **Settings** → **Connections** → **+ Add Connection**

### 2. Enter Configuration
- **Name**: Can be anything descriptive (e.g., "Payment Team", "Data Analysts")
- **URL**: Use the appropriate group URL from the table above
- **Auth**: Bearer
- **Bearer Token**: Your API key
- **Visibility**: Public/Private as needed

**Important**: The display name in Open WebUI is just for organization - only the URL path determines which tools are available.

### 3. Save and Test
Click **Save** - connection should succeed immediately. Invalid group paths will return an error.

## Getting Your API Key

```bash
# Retrieve the API key from GCP Secret Manager
gcloud secrets versions access latest \
  --secret="OPEN_WEBUI_API_KEY" \
  --project=popfly-mcp-servers
```

## Available Tools

Tools are dynamically loaded from the database based on group membership:

| Tool | Description | Groups | Example Usage |
|------|-------------|--------|---------------|
| `query_payments` | Natural language payment queries using AI | Admins, Account Managers | "Show me total payments by month" |

**Note**: `read_query` is an internal-only tool used by `query_payments` to execute generated SQL. It's not exposed directly to prevent arbitrary SQL execution.

**Note**: Additional tools can be added to the database without code changes. The system is fully dynamic.

## Troubleshooting

### Connection Failed Error

**Common Causes**:

1. **Incorrect URL format**:
   - ❌ **WRONG**: `https://mcp.popfly.com/openapi.json`
   - ❌ **WRONG**: `https://mcp.popfly.com/`  
   - ✅ **CORRECT**: `https://mcp.popfly.com/admins/tools` (for admin group)
   - ✅ **CORRECT**: `https://mcp.popfly.com/tools` (for default group)

2. **Invalid group path**:
   - ❌ **WRONG**: `https://mcp.popfly.com/adminssss/tools` (returns 404)
   - The server validates group paths and returns: "Unknown group: adminssss. Valid groups are: default, admins, accountmanagers"

### Check Server Status

```bash
# Health check (no auth required)
curl https://mcp.popfly.com/health

# List tools for different groups (requires auth)
API_KEY=$(gcloud secrets versions access latest \
  --secret="OPEN_WEBUI_API_KEY" \
  --project=popfly-mcp-servers)

# Default group tools  
curl -H "Authorization: Bearer $API_KEY" \
  https://mcp.popfly.com/tools

# Admin group tools
curl -H "Authorization: Bearer $API_KEY" \
  https://mcp.popfly.com/admins/tools

# Account Manager tools  
curl -H "Authorization: Bearer $API_KEY" \
  https://mcp.popfly.com/accountmanagers/tools
```

### View Server Logs

```bash
# Recent HTTP service logs
gcloud compute ssh mcp-snowflake-vm \
  --zone=us-central1-a \
  --project=popfly-mcp-servers \
  --command="sudo journalctl -u mcp-http -n 50 --no-pager"
```

### Common Issues

1. **401 Unauthorized**: Invalid or missing bearer token
2. **404 on //openapi.json**: URL includes path (remove `/openapi.json`)
3. **CORS errors**: Check browser console, server allows all origins
4. **502 Bad Gateway**: Service down, restart with:
   ```bash
   gcloud compute ssh mcp-snowflake-vm \
     --zone=us-central1-a \
     --project=popfly-mcp-servers \
     --command="sudo systemctl restart mcp-http"
   ```

## Security Notes

- Bearer token is stored securely in GCP Secret Manager
- All traffic is encrypted via HTTPS
- Snowflake connection uses RSA key authentication
- IP whitelisting enforced at Snowflake level

## Server Details

- **URL**: https://mcp.popfly.com
- **IP**: 104.198.62.220
- **SSL**: Let's Encrypt (auto-renews)
- **Project**: popfly-mcp-servers
- **VM**: mcp-snowflake-vm (us-central1-a)

## For Developers

### Testing Tools Directly

```bash
# Get API key
API_KEY=$(gcloud secrets versions access latest \
  --secret="OPEN_WEBUI_API_KEY" \
  --project=popfly-mcp-servers)

# Test a tool
curl -X POST https://mcp.popfly.com/tools/call \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "list_databases",
    "arguments": {}
  }'
```

### OpenAPI Specification

The API specification is available per group:

```bash
# Default group
https://mcp.popfly.com/openapi.json

# Admin group
https://mcp.popfly.com/admins/tools/openapi.json

# Account Managers group
https://mcp.popfly.com/accountmanagers/tools/openapi.json
```

Each specification reflects the tools available to that specific group. These can be imported into tools like Postman or Swagger UI for testing.