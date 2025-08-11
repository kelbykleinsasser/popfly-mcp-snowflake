# Current Deployment Architecture - VM-Based MCP Server

**Last Updated**: 2025-08-11  
**Deployment Type**: GCP VM with HTTP-based MCP for Open WebUI  
**Status**: ✅ Production Ready

## Overview

The Snowflake MCP server is deployed on a dedicated GCP Virtual Machine in the `popfly-mcp-servers` project, providing an HTTP API for Open WebUI integration. This replaces the previous container-based Cloud Run deployment that had numerous issues with cold starts, dynamic IPs, and HTTP/HTTPS complexity.

## Infrastructure Details

### GCP Resources
- **Project**: `popfly-mcp-servers`
- **VM Name**: `mcp-snowflake-vm`
- **Zone**: `us-central1-a`
- **Machine Type**: `e2-medium` (2 vCPUs, 4GB RAM)
- **Static IP**: `104.198.62.220`
- **Domain**: `mcp.popfly.com` (A record pointing to 104.198.62.220)
- **SSL Certificate**: Let's Encrypt via Certbot
- **Service Account**: `mcp-snowflake-vm@popfly-mcp-servers.iam.gserviceaccount.com`
- **OS**: Ubuntu 22.04 LTS
- **Python**: 3.11

### Snowflake Configuration
- **Network Rule**: `ALLOW_POPFLY_MCP`
- **Allowed IPs**: `('216.16.8.56', '104.198.62.220')`
  - `216.16.8.56` - Development machine
  - `104.198.62.220` - Production VM

### File Locations on VM
- **MCP Server Code**: `/opt/mcp-snowflake/`
- **Python Virtual Environment**: `/opt/mcp-snowflake/venv/`
- **Run Script**: `/opt/mcp-snowflake/run_mcp.sh`
- **Systemd Service**: `/etc/systemd/system/mcp-http.service`
- **Nginx Config**: `/etc/nginx/sites-available/mcp-snowflake`

## Secrets Management

All secrets are stored in GCP Secret Manager in the `popfly-mcp-servers` project:

- `SNOWFLAKE_ACCOUNT` - Snowflake account identifier
- `SNOWFLAKE_USER` - MCP_POPFLY_SNOWFLAKE user
- `SNOWFLAKE_PRIVATE_KEY` - RSA private key for authentication
- `SNOWFLAKE_DATABASE` - PF
- `SNOWFLAKE_SCHEMA` - BI
- `SNOWFLAKE_WAREHOUSE` - COMPUTE_WH
- `SNOWFLAKE_ROLE` - MCP_ROLE

The `config/settings.py` file automatically loads these secrets when `USE_GCP_SECRETS=true` is set.

## Deployment Process

### Quick Deploy (After Changes)

```bash
# From local development machine
./deploy_to_vm.sh
```

This script:
1. Creates a tar archive of the code (excluding .git, venv, etc.)
2. Uploads to VM via gcloud SCP
3. Extracts on VM
4. Updates Python dependencies
5. Takes ~10 seconds total

### Manual Deployment Steps

If you need to deploy manually:

```bash
# 1. Create archive locally
tar -czf /tmp/mcp-deployment.tar.gz \
    --exclude='.git' \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.env' \
    --exclude='*.log' \
    .

# 2. Copy to VM
gcloud compute scp /tmp/mcp-deployment.tar.gz \
    mcp-snowflake-vm:/tmp/mcp-deployment.tar.gz \
    --zone=us-central1-a \
    --project=popfly-mcp-servers

# 3. SSH to VM and extract
gcloud compute ssh mcp-snowflake-vm --zone=us-central1-a --project=popfly-mcp-servers
cd /opt/mcp-snowflake
tar -xzf /tmp/mcp-deployment.tar.gz
source venv/bin/activate
pip install -r requirements.txt
```

## How the MCP Server Works

### Architecture
1. **Protocol**: HTTPS with FastAPI backend
2. **Service**: Always-on systemd service (`mcp-http.service`)
3. **Proxy**: Nginx reverse proxy with SSL termination
4. **Authentication**: Bearer token for API access + RSA key pair for Snowflake
5. **Secrets**: Loaded from GCP Secret Manager at runtime

### Connection Flow
1. Open WebUI makes HTTPS request to `https://mcp.popfly.com`
2. Nginx handles SSL and proxies to localhost:8000
3. FastAPI server authenticates bearer token
4. Server loads secrets from GCP Secret Manager
5. Server connects to Snowflake using RSA authentication
6. Response returned as JSON to Open WebUI

### Available HTTP Endpoints
- `GET /` - Server information
- `GET /health` - Health check
- `GET /tools` - List available MCP tools
- `POST /tools/call` - Execute a specific tool
- `GET /openapi.json` - OpenAPI specification
- `GET /diagnostics` - Run diagnostics (authenticated)

### Open WebUI Configuration

**IMPORTANT**: Enter ONLY the base URL in Open WebUI's connection dialog!

**Correct Configuration in Edit Connection Dialog:**
- **URL**: `https://mcp.popfly.com` (⚠️ BASE URL ONLY - no `/openapi.json`)
- **Auth**: Bearer
- **Bearer Token**: Get from GCP Secret Manager (`OPEN_WEBUI_API_KEY`)
- **Name**: Popfly MCP
- **Description**: Snowflake database tools
- **Visibility**: Public (or as needed)

**Common Mistake to Avoid:**
- ❌ **WRONG**: `https://mcp.popfly.com/openapi.json` 
- ✅ **RIGHT**: `https://mcp.popfly.com`

Open WebUI automatically appends `/openapi.json` to fetch the spec.

**Available Tools:**
- `list_databases` - List all Snowflake databases
- `list_schemas` - List schemas in a database
- `list_tables` - List tables in a schema
- `describe_table` - Get table schema information
- `read_query` - Execute SELECT queries
- `append_insight` - Log data insights
- `query_payments` - Natural language payment queries (Cortex)

## Maintenance Operations

### SSH to VM
```bash
gcloud compute ssh mcp-snowflake-vm --zone=us-central1-a --project=popfly-mcp-servers
```

### View Server Logs
```bash
# View HTTP service logs
gcloud compute ssh mcp-snowflake-vm --zone=us-central1-a --project=popfly-mcp-servers --command="sudo journalctl -u mcp-http -f"

# View nginx logs
gcloud compute ssh mcp-snowflake-vm --zone=us-central1-a --project=popfly-mcp-servers --command="sudo tail -f /var/log/nginx/access.log"
```

### Restart Services
```bash
# Restart HTTP service
gcloud compute ssh mcp-snowflake-vm --zone=us-central1-a --project=popfly-mcp-servers --command="sudo systemctl restart mcp-http"

# Restart nginx
gcloud compute ssh mcp-snowflake-vm --zone=us-central1-a --project=popfly-mcp-servers --command="sudo systemctl restart nginx"
```

### Test HTTP API
```bash
# Get API key
API_KEY=$(gcloud secrets versions access latest --secret="OPEN_WEBUI_API_KEY" --project=popfly-mcp-servers)

# Test health endpoint
curl https://mcp.popfly.com/health

# List available tools
curl -H "Authorization: Bearer $API_KEY" https://mcp.popfly.com/tools

# Execute a tool
curl -X POST -H "Authorization: Bearer $API_KEY" \
     -H "Content-Type: application/json" \
     https://mcp.popfly.com/tools/call \
     -d '{"name": "list_databases", "arguments": {}}'
```

### Test Snowflake Connection
```bash
# SSH to VM first, then:
cd /opt/mcp-snowflake
source venv/bin/activate
export USE_GCP_SECRETS=true
export GCP_PROJECT_ID=popfly-mcp-servers
export ENVIRONMENT=production
python -c "from utils.config import get_environment_snowflake_connection; conn = get_environment_snowflake_connection(); print('Connected!'); conn.close()"
```

### Update Secrets
```bash
# Example: Update Snowflake user
echo -n "NEW_USER_NAME" | gcloud secrets versions add SNOWFLAKE_USER --data-file=- --project=popfly-mcp-servers
```

### Restart VM (if needed)
```bash
gcloud compute instances reset mcp-snowflake-vm --zone=us-central1-a --project=popfly-mcp-servers
```

## Troubleshooting

### Common Issues

1. **"User is empty" error**
   - Check that `USE_GCP_SECRETS=true` is set
   - Check that `GCP_PROJECT_ID=popfly-mcp-servers` is set
   - Verify VM has access to secrets: `gcloud secrets versions access latest --secret=SNOWFLAKE_USER --project=popfly-mcp-servers`

2. **Connection refused from Snowflake**
   - Verify VM IP is in Snowflake network rule: `SHOW NETWORK RULES LIKE 'ALLOW_POPFLY_MCP';`
   - Check static IP hasn't changed: `gcloud compute instances describe mcp-snowflake-vm --zone=us-central1-a --project=popfly-mcp-servers --format="get(networkInterfaces[0].accessConfigs[0].natIP)"`

3. **MCP server won't start**
   - Check Python dependencies: `pip list`
   - Verify virtual environment is activated
   - Check for syntax errors: `python -m py_compile server/mcp_server.py`

4. **Deployment fails**
   - Ensure you have proper GCP permissions
   - Check that VM has enough disk space: `df -h`
   - Verify network connectivity

### Debug Commands

```bash
# Check VM status
gcloud compute instances describe mcp-snowflake-vm --zone=us-central1-a --project=popfly-mcp-servers

# List secrets
gcloud secrets list --project=popfly-mcp-servers

# Check service account permissions
gcloud projects get-iam-policy popfly-mcp-servers --flatten="bindings[].members" --filter="bindings.members:mcp-snowflake-vm@popfly-mcp-servers.iam.gserviceaccount.com"

# Test secret access from VM
gcloud compute ssh mcp-snowflake-vm --zone=us-central1-a --project=popfly-mcp-servers --command="gcloud secrets versions access latest --secret=SNOWFLAKE_USER --project=popfly-mcp-servers"
```

## Important Notes for Future Sessions

### Critical Information
1. **This IS an HTTP service** - FastAPI server behind Nginx with SSL
2. **Systemd service running** - `mcp-http.service` runs continuously
3. **DNS is active** - `mcp.popfly.com` A record points to 104.198.62.220
4. **SSL Certificate** - Managed by Let's Encrypt, auto-renews via Certbot
5. **Secrets auto-load** - The `config/settings.py` handles GCP Secret Manager automatically
6. **Static IP is crucial** - Must be in Snowflake's `ALLOW_POPFLY_MCP` network rule

### What Was Removed
- All container artifacts (Dockerfile, cloudbuild.yaml, docker-compose.yml)
- Cloud Run service and associated infrastructure
- Old static IP from `popfly-open-webui` project (34.63.149.139)
- VPC Connector, Cloud NAT, Cloud Router from old project

### Key Files Modified
- `config/settings.py` - Added GCP Secret Manager integration
- `utils/config.py` - Uses new settings with secret loading
- Created `deploy_to_vm.sh` for easy deployments
- Created `/opt/mcp-snowflake/run_mcp.sh` on VM for running server

### Migration Date
- **2025-08-11**: Migrated from Cloud Run to VM-based deployment
- Previous Cloud Run deployment had issues with:
  - Dynamic IPs requiring complex NAT setup
  - Cold starts affecting performance
  - Container lifecycle complications
  - HTTP/HTTPS overhead for stdio protocol

## Cost Considerations

- **VM**: ~$50/month for e2-medium always-on
- **Static IP**: ~$7/month when attached to VM
- **Secrets Manager**: Minimal cost for secret storage
- **Total**: ~$60/month (vs ~$30/month for Cloud Run but with many issues)

## Security Notes

1. **Network Security**
   - VM only accessible via GCP IAM (no direct SSH with keys)
   - Static IP whitelisted in Snowflake
   - Secrets never exposed in environment variables directly

2. **Authentication**
   - RSA key pair for Snowflake (no passwords)
   - GCP IAM for VM access
   - Service account with minimal permissions

3. **Best Practices**
   - Never commit secrets to git
   - Always use Secret Manager for sensitive data
   - Regularly rotate RSA keys if needed
   - Monitor access logs

## Related Documentation

- `deployment/LESSONS.md` - Historical issues and solutions
- `deployment/deployment_instructions_mcp.md` - Generic VM deployment guide
- `CLAUDE.md` - Project-specific implementation guide
- `deploy_to_vm.sh` - Deployment automation script

---

**Remember**: This is an HTTP-based MCP server running on a VM, providing a REST API for Open WebUI integration. The server runs continuously as a systemd service behind Nginx with SSL.