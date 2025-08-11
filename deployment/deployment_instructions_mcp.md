# VM Deployment Instructions for MCP Services

## Overview
This guide documents the process of deploying MCP (Model Context Protocol) services to GCP VMs instead of containerized environments. This approach provides better stability, simpler deployment, and easier troubleshooting for long-running MCP services.

## Why VM Deployment for MCP Services?
- **Persistent environment**: No cold starts or container recycling issues
- **Direct SSH access**: Easy debugging and monitoring of MCP server logs
- **Simpler secrets management**: Direct file system access for credentials
- **Faster deployments**: 10-second rsync vs multi-minute container builds
- **Better for MCP servers**: Designed for always-on connection handling
- **Cost effective**: Predictable pricing with always-on small instance

## Prerequisites

### 1. GCP Project Setup
```bash
# Set your project ID
export GCP_PROJECT_ID="your-project-id"
gcloud config set project $GCP_PROJECT_ID

# Enable required APIs
gcloud services enable compute.googleapis.com
gcloud services enable secretmanager.googleapis.com
```

### 2. Service Account & Permissions
```bash
# Create service account for the VM
gcloud iam service-accounts create mcp-snowflake-vm \
    --display-name="MCP Snowflake VM Service Account"

# Grant necessary permissions
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
    --member="serviceAccount:mcp-snowflake-vm@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

## Step 1: Create and Configure VM

### Create VM Instance
```bash
gcloud compute instances create mcp-snowflake-vm \
    --zone=us-central1-a \
    --machine-type=e2-medium \
    --network-interface=network-tier=PREMIUM,subnet=default \
    --metadata=enable-oslogin=true \
    --maintenance-policy=MIGRATE \
    --service-account=mcp-snowflake-vm@${GCP_PROJECT_ID}.iam.gserviceaccount.com \
    --scopes=https://www.googleapis.com/auth/cloud-platform \
    --create-disk=auto-delete=yes,boot=yes,device-name=mcp-snowflake-vm,image=projects/ubuntu-os-cloud/global/images/family/ubuntu-2204-lts,mode=rw,size=20,type=pd-standard \
    --reservation-affinity=any
```

### Reserve Static IP (Required for Snowflake)
```bash
# Reserve a static external IP
gcloud compute addresses create mcp-snowflake-static-ip \
    --region=us-central1

# Get the IP address
gcloud compute addresses describe mcp-snowflake-static-ip \
    --region=us-central1 --format="get(address)"

# Attach to VM
gcloud compute instances delete-access-config mcp-snowflake-vm \
    --zone=us-central1-a
    
gcloud compute instances add-access-config mcp-snowflake-vm \
    --zone=us-central1-a \
    --address=[STATIC_IP_ADDRESS]
```

### Update Snowflake Network Rules
Add the VM's static IP to the existing `ALLOW_POPFLY_MCP` network rule:

```sql
-- Get current IPs in the ALLOW_POPFLY_MCP rule
SHOW NETWORK RULES LIKE 'ALLOW_POPFLY_MCP';

-- Update the network rule to include the new VM IP
ALTER NETWORK RULE ALLOW_POPFLY_MCP
    SET VALUE_LIST = ('[EXISTING_IPS]', '[NEW_STATIC_IP_ADDRESS]');

-- Verify the update
SHOW NETWORK RULES LIKE 'ALLOW_POPFLY_MCP';
```

Note: If `ALLOW_POPFLY_MCP` doesn't exist yet, create it:
```sql
CREATE NETWORK RULE ALLOW_POPFLY_MCP
    MODE = INGRESS
    TYPE = IPV4
    VALUE_LIST = ('[STATIC_IP_ADDRESS]');
```

## Step 2: Initial VM Setup

### SSH into VM and Install Dependencies
```bash
# SSH into the VM
gcloud compute ssh mcp-snowflake-vm --zone=us-central1-a

# Once connected, run these commands:
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv python3-pip git

# Install Node.js if your MCP server uses TypeScript/JavaScript
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Create project directory
sudo mkdir -p /opt/mcp-snowflake
sudo chown $USER:$USER /opt/mcp-snowflake

# Clone your repository (or prepare for deployment)
cd /opt/mcp-snowflake
git clone https://github.com/your-org/popfly-mcp-snowflake.git .
# OR create directory structure for deployment

# Setup Python environment (for Python MCP servers)
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip

# OR Setup Node environment (for TypeScript/JavaScript MCP servers)
npm install
```

## Step 3: Create Deployment Scripts

### Create deploy_to_vm.sh (Local Machine)
```bash
#!/bin/bash
set -e

# Configuration
VM_NAME="mcp-snowflake-vm"
VM_ZONE="us-central1-a"
REMOTE_DIR="/opt/mcp-snowflake"
LOCAL_DIR="."

echo "🚀 Starting MCP server deployment to VM..."

# Create tar archive excluding unnecessary files
echo "📦 Creating deployment archive..."
tar -czf /tmp/mcp-deployment.tar.gz \
    --exclude='.git' \
    --exclude='venv' \
    --exclude='node_modules' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.env' \
    --exclude='*.log' \
    --exclude='dist' \
    --exclude='build' \
    .

# Copy to VM
echo "📤 Uploading to VM..."
gcloud compute scp /tmp/mcp-deployment.tar.gz \
    $VM_NAME:/tmp/mcp-deployment.tar.gz \
    --zone=$VM_ZONE

# Extract and restart service
echo "🔄 Extracting and restarting MCP server..."
gcloud compute ssh $VM_NAME --zone=$VM_ZONE --command="
    cd $REMOTE_DIR && \
    tar -xzf /tmp/mcp-deployment.tar.gz && \
    source venv/bin/activate && \
    pip install -r requirements.txt && \
    sudo systemctl restart mcp-snowflake && \
    sudo systemctl status mcp-snowflake
"

# Cleanup
rm /tmp/mcp-deployment.tar.gz

echo "✅ MCP server deployment complete!"
echo "📊 View logs with: gcloud compute ssh $VM_NAME --zone=$VM_ZONE --command='sudo journalctl -u mcp-snowflake -f'"
```

### Create systemd Service File for MCP Server (On VM)
```bash
# Create service file for Python MCP server
sudo tee /etc/systemd/system/mcp-snowflake.service << 'EOF'
[Unit]
Description=MCP Snowflake Server
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/mcp-snowflake
Environment="PATH=/opt/mcp-snowflake/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="USE_GCP_SECRETS=true"
Environment="MCP_MODE=stdio"
ExecStart=/opt/mcp-snowflake/venv/bin/python -m mcp_server
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable mcp-snowflake
sudo systemctl start mcp-snowflake
```

## Step 4: MCP Server Configuration

### Create MCP Server Entry Point (Python Example)
```python
# mcp_server.py
import asyncio
import json
from mcp import Server, Tool
from mcp.server.stdio import stdio_server
from typing import Any, Dict
import snowflake.connector
from secrets_manager import SecretsManager

# Initialize MCP server
app = Server("snowflake-mcp")
secrets = SecretsManager()

# Define MCP tools
@app.tool()
async def query_snowflake(query: str) -> Dict[str, Any]:
    """Execute a Snowflake query"""
    config = secrets.get_snowflake_config()
    
    conn = snowflake.connector.connect(**config)
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        return {
            "columns": columns,
            "rows": [dict(zip(columns, row)) for row in results],
            "row_count": len(results)
        }
    finally:
        conn.close()

@app.tool()
async def list_databases() -> Dict[str, Any]:
    """List all accessible Snowflake databases"""
    return await query_snowflake("SHOW DATABASES")

@app.tool()
async def list_tables(database: str, schema: str = "PUBLIC") -> Dict[str, Any]:
    """List tables in a specific database and schema"""
    query = f"SHOW TABLES IN {database}.{schema}"
    return await query_snowflake(query)

# Run the MCP server
def main():
    """Run the MCP server using stdio transport"""
    asyncio.run(stdio_server(app).run())

if __name__ == "__main__":
    main()
```

## Step 5: Secrets Management for MCP

### Setup GCP Secret Manager
```bash
# Create secrets (run from local machine)
echo -n "your-snowflake-account" | gcloud secrets create SNOWFLAKE_ACCOUNT --data-file=-
echo -n "your-snowflake-user" | gcloud secrets create SNOWFLAKE_USER --data-file=-
echo -n "your-snowflake-password" | gcloud secrets create SNOWFLAKE_PASSWORD --data-file=-
echo -n "your-snowflake-warehouse" | gcloud secrets create SNOWFLAKE_WAREHOUSE --data-file=-
echo -n "your-snowflake-database" | gcloud secrets create SNOWFLAKE_DATABASE --data-file=-
echo -n "your-snowflake-schema" | gcloud secrets create SNOWFLAKE_SCHEMA --data-file=-
```

### Create secrets_manager.py
```python
import os
from typing import Dict, Any
from google.cloud import secretmanager

class SecretsManager:
    def __init__(self):
        self.use_gcp = os.getenv('USE_GCP_SECRETS', 'false').lower() == 'true'
        self.project_id = os.getenv('GCP_PROJECT_ID')
        
        if self.use_gcp:
            self.client = secretmanager.SecretManagerServiceClient()
    
    def get_secret(self, secret_name: str) -> str:
        """Get secret from GCP Secret Manager or environment"""
        if self.use_gcp:
            name = f"projects/{self.project_id}/secrets/{secret_name}/versions/latest"
            response = self.client.access_secret_version(request={"name": name})
            return response.payload.data.decode("UTF-8").strip()
        else:
            # Fall back to environment variables for local development
            return os.getenv(secret_name, "")
    
    def get_snowflake_config(self) -> Dict[str, Any]:
        """Get Snowflake configuration from secrets"""
        return {
            "account": self.get_secret("SNOWFLAKE_ACCOUNT"),
            "user": self.get_secret("SNOWFLAKE_USER"),
            "password": self.get_secret("SNOWFLAKE_PASSWORD"),
            "warehouse": self.get_secret("SNOWFLAKE_WAREHOUSE"),
            "database": self.get_secret("SNOWFLAKE_DATABASE"),
            "schema": self.get_secret("SNOWFLAKE_SCHEMA"),
        }
```

## Step 6: MCP Client Configuration

### Configure Claude Desktop (or other MCP clients)
Add to your MCP client configuration:
```json
{
  "mcpServers": {
    "snowflake-prod": {
      "command": "gcloud",
      "args": [
        "compute",
        "ssh",
        "mcp-snowflake-vm",
        "--zone=us-central1-a",
        "--command",
        "cd /opt/mcp-snowflake && source venv/bin/activate && python -m mcp_server"
      ]
    }
  }
}
```

### For Remote Access via SSH Tunnel
```json
{
  "mcpServers": {
    "snowflake-prod": {
      "command": "ssh",
      "args": [
        "-o",
        "StrictHostKeyChecking=no",
        "ubuntu@[STATIC_IP_ADDRESS]",
        "cd /opt/mcp-snowflake && source venv/bin/activate && python -m mcp_server"
      ]
    }
  }
}
```

## Step 7: Monitoring and Maintenance

### View MCP Server Logs
```bash
# Real-time logs
gcloud compute ssh mcp-snowflake-vm --zone=us-central1-a \
    --command="sudo journalctl -u mcp-snowflake -f"

# Last 100 lines
gcloud compute ssh mcp-snowflake-vm --zone=us-central1-a \
    --command="sudo journalctl -u mcp-snowflake -n 100"

# Check for errors
gcloud compute ssh mcp-snowflake-vm --zone=us-central1-a \
    --command="sudo journalctl -u mcp-snowflake -p err -n 50"
```

### Service Management
```bash
# Restart MCP server
gcloud compute ssh mcp-snowflake-vm --zone=us-central1-a \
    --command="sudo systemctl restart mcp-snowflake"

# Check status
gcloud compute ssh mcp-snowflake-vm --zone=us-central1-a \
    --command="sudo systemctl status mcp-snowflake"

# Stop MCP server
gcloud compute ssh mcp-snowflake-vm --zone=us-central1-a \
    --command="sudo systemctl stop mcp-snowflake"
```

### Quick Deployment After Changes
```bash
# Deploy in ~10 seconds
./deploy_to_vm.sh
```

## Step 8: Health Monitoring for MCP

### Create Health Check Endpoint (Optional)
```python
# health_check.py
import asyncio
import snowflake.connector
from secrets_manager import SecretsManager
from fastapi import FastAPI
import uvicorn

app = FastAPI()
secrets = SecretsManager()

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    try:
        config = secrets.get_snowflake_config()
        conn = snowflake.connector.connect(**config)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        conn.close()
        return {"status": "healthy", "snowflake": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}, 503

# Run on a separate port
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
```

## Troubleshooting MCP Services

### Common Issues and Solutions

1. **MCP Server Won't Start**
   - Check logs: `sudo journalctl -u mcp-snowflake -n 50`
   - Verify Python/Node path and environment
   - Ensure MCP dependencies are installed
   - Check stdio mode is correctly configured

2. **Client Can't Connect to MCP Server**
   - Verify SSH access to VM
   - Check service is running: `systemctl status mcp-snowflake`
   - Test MCP server locally on VM first
   - Ensure gcloud SSH is properly configured

3. **Snowflake Connection Issues**
   - Verify static IP is in `ALLOW_POPFLY_MCP` network rule
   - Check secrets don't have trailing whitespace
   - Test connection directly on VM
   - Verify warehouse is running

4. **MCP Tool Execution Errors**
   - Check tool permissions in Snowflake
   - Verify query syntax
   - Monitor memory usage on VM
   - Check for rate limiting

## Performance Optimization

### For MCP Servers
- **Connection Pooling**: Implement Snowflake connection pooling
- **Caching**: Cache frequently accessed metadata
- **Async Operations**: Use async/await for all I/O operations
- **Resource Limits**: Set appropriate query timeouts and row limits

### VM Sizing
- **e2-micro**: Testing and development
- **e2-small**: Light production workloads
- **e2-medium**: Standard production (recommended)
- **e2-standard-2**: Heavy workloads with multiple concurrent users

## Security Best Practices for MCP

1. **API Keys**: Never expose Snowflake credentials in MCP responses
2. **Query Validation**: Sanitize and validate all SQL queries
3. **Row Limits**: Implement default row limits to prevent large data transfers
4. **Audit Logging**: Log all MCP tool invocations
5. **Network Security**: Restrict VM access to specific IPs if possible
6. **Regular Updates**: Keep MCP server dependencies updated

## Migration Checklist

- [ ] Create GCP VM instance
- [ ] Reserve and attach static IP
- [ ] Add IP to `ALLOW_POPFLY_MCP` network rule in Snowflake
- [ ] Setup Python/Node environment on VM
- [ ] Deploy MCP server code
- [ ] Configure systemd service
- [ ] Setup GCP Secret Manager
- [ ] Test MCP server locally on VM
- [ ] Configure MCP client connections
- [ ] Test end-to-end MCP functionality
- [ ] Setup monitoring and alerting
- [ ] Document available MCP tools

## Benefits for MCP Services

- **Always Available**: MCP server runs 24/7 without cold starts
- **Direct Debugging**: SSH into VM to debug MCP server issues
- **Fast Updates**: Deploy changes in seconds
- **Cost Effective**: Predictable costs for always-on service
- **Better Logging**: Centralized logging with journald
- **Network Stability**: Static IP ensures consistent Snowflake access

## Network Rule Reference

The `ALLOW_POPFLY_MCP` network rule is used across multiple Popfly services for Snowflake access. When adding new services:

1. Always check existing IPs first: `SHOW NETWORK RULES LIKE 'ALLOW_POPFLY_MCP';`
2. Add new IPs to the existing rule rather than creating new rules
3. Document which IP belongs to which service for future reference
4. Consider creating a tracking table or document with IP-to-service mappings

---

*This deployment pattern provides a robust, maintainable solution for production MCP services with direct database access.*