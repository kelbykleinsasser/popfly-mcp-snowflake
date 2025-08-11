# Deployment Lessons Learned

## Cloud Run to Snowflake Connection Issues (2025-08-08)

### Problem: Dynamic IP Addresses Blocked by Snowflake Network Policy

**Symptoms:**
- Error: `250001 (08001): Failed to connect to DB: ycwwtpd-xa25231.snowflakecomputing.com:443. Incoming request with IP/Token 34.96.47.93 is not allowed to access Snowflake`
- Cloud Run service kept getting blocked with different IPs on each deployment/request
- IPs observed: `34.96.47.93`, `34.34.233.206`, `34.96.45.244`

**Root Cause:**
- Cloud Run services use dynamic egress IP addresses from a pool
- Each deployment or even each request could use a different IP
- Snowflake network policies require whitelisted IPs for security

**Solution: Set up Cloud NAT with Static IP**

1. **Reserve a static external IP:**
```bash
gcloud compute addresses create snowflake-mcp-nat-ip \
  --region=us-central1 \
  --project=popfly-open-webui
  
# Get the IP address (resulted in: 34.63.149.139)
gcloud compute addresses describe snowflake-mcp-nat-ip \
  --region=us-central1 \
  --project=popfly-open-webui \
  --format="value(address)"
```

2. **Create Cloud Router:**
```bash
gcloud compute routers create snowflake-mcp-router \
  --network=default \
  --region=us-central1 \
  --project=popfly-open-webui
```

3. **Create Cloud NAT gateway:**
```bash
gcloud compute routers nats create snowflake-mcp-nat \
  --router=snowflake-mcp-router \
  --region=us-central1 \
  --nat-external-ip-pool=snowflake-mcp-nat-ip \
  --nat-all-subnet-ip-ranges \
  --project=popfly-open-webui
```

4. **Enable VPC Access API (if not already enabled):**
```bash
gcloud services enable vpcaccess.googleapis.com --project=popfly-open-webui
```

5. **Create Serverless VPC Connector:**
```bash
gcloud compute networks vpc-access connectors create snowflake-mcp-connector \
  --region=us-central1 \
  --network=default \
  --range=10.8.0.0/28 \
  --max-instances=10 \
  --project=popfly-open-webui
  
# Note: This can take 2-3 minutes to become READY
# Check status with:
gcloud compute networks vpc-access connectors describe snowflake-mcp-connector \
  --region=us-central1 \
  --project=popfly-open-webui \
  --format="value(state)"
```

6. **Update Cloud Run service to use VPC Connector:**
```bash
gcloud run services update snowflake-mcp-server \
  --vpc-connector=snowflake-mcp-connector \
  --vpc-egress=all-traffic \
  --region=us-central1 \
  --project=popfly-open-webui
```

7. **Update Snowflake network policy to allow only the static IP:**
```sql
ALTER NETWORK POLICY POPFLY_MCP_POLICY SET 
    ALLOWED_IP_LIST = ('34.63.149.139');
```

---

### Problem: JWT Token Invalid Error After IP Was Whitelisted

**Symptoms:**
- Error: `250001 (08001): Failed to connect to DB: ycwwtpd-xa25231.snowflakecomputing.com:443. JWT token is invalid`
- This occurred even though the same key worked locally
- Happened after resolving IP whitelisting issues

**Root Causes:**

1. **User Mismatch:**
   - The deployment was using user `MCP_POPFLY_SNOWFLAKE` but the private key in GCP secrets was for the old user `SVC_POPFLY_APP`
   - Each Snowflake user has their own RSA key pair

2. **Secret Formatting Issues:**
   - **Trailing newlines** in secrets caused authentication failures
   - `SNOWFLAKE_USER` secret had a trailing newline
   - `SNOWFLAKE_PRIVATE_KEY_PATH` secret had improper formatting

**Detection Commands:**
```bash
# Check for trailing newlines in user secret
gcloud secrets versions access latest --secret="SNOWFLAKE_USER" --project=popfly-open-webui | od -c
# Output showed: M C P _ P O P F L Y _ S N O W F L A K E \n

# Check private key formatting
gcloud secrets versions access latest --secret="SNOWFLAKE_PRIVATE_KEY_PATH" --project=popfly-open-webui | od -c | tail -3
# Output showed trailing \n after -----END PRIVATE KEY-----
```

**Solution:**

1. **Generate new RSA key pair for the correct user:**
```bash
# Generate private key
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out snowflake_key_mcp.pem -nocrypt

# Generate public key
openssl rsa -in snowflake_key_mcp.pem -pubout -out snowflake_key_mcp.pub

# Extract public key without headers for Snowflake
cat snowflake_key_mcp.pub | grep -v "BEGIN PUBLIC KEY" | grep -v "END PUBLIC KEY" | tr -d '\n'
```

2. **Set public key in Snowflake:**
```sql
ALTER USER MCP_POPFLY_SNOWFLAKE SET RSA_PUBLIC_KEY='<paste public key here>';
```

3. **Update GCP secrets WITHOUT trailing newlines:**
```bash
# Update user secret without newline
echo -n "MCP_POPFLY_SNOWFLAKE" | gcloud secrets versions add SNOWFLAKE_USER --data-file=- --project=popfly-open-webui

# Update private key with proper formatting (no trailing newline)
cat /path/to/snowflake_key_mcp.pem | tr -d '\n' | \
  sed 's/-----BEGIN PRIVATE KEY-----/-----BEGIN PRIVATE KEY-----\n/' | \
  sed 's/-----END PRIVATE KEY-----/\n-----END PRIVATE KEY-----/' | \
  fold -w 64 | \
  gcloud secrets versions add SNOWFLAKE_PRIVATE_KEY_PATH --data-file=- --project=popfly-open-webui
```

4. **Update Cloud Run with new secret versions:**
```bash
gcloud run services update snowflake-mcp-server \
  --region=us-central1 \
  --update-secrets=SNOWFLAKE_USER=SNOWFLAKE_USER:2,SNOWFLAKE_PRIVATE_KEY=SNOWFLAKE_PRIVATE_KEY_PATH:4 \
  --project=popfly-open-webui
```

---

### Problem: Secrets Stored as File Paths Instead of Content

**Initial Issue:**
- The `SNOWFLAKE_PRIVATE_KEY_PATH` secret contained a file path instead of the actual key content
- Cloud Run cannot access local file paths

**Solution:**
- Store the actual private key content in the secret, not the file path:
```bash
cat /path/to/private_key.pem | gcloud secrets versions add SNOWFLAKE_PRIVATE_KEY_PATH --data-file=- --project=popfly-open-webui
```

---

## Key Learnings and Best Practices

### 1. Always Use Static IPs for Cloud Run → External Services
- Cloud Run uses dynamic IPs by default
- For services requiring IP whitelisting (like Snowflake), always set up Cloud NAT with static IP
- This ensures consistent, predictable connectivity

### 2. Secret Formatting is Critical
- **NEVER include trailing newlines** in secrets unless explicitly required
- Use `echo -n` or proper text processing to remove newlines
- Always verify secret content with `od -c` to check for hidden characters
- Test format: `gcloud secrets versions access latest --secret=SECRET_NAME | od -c`

### 3. RSA Key Pair Management
- Each Snowflake user needs their own RSA key pair
- Public key goes in Snowflake (via ALTER USER)
- Private key (full PEM content, not path) goes in GCP Secret Manager
- Keep local copies in `auth/keys/` directory for reference
- Add `*.pem` to `.gitignore` to prevent accidental commits

### 4. Debugging Connection Issues - Order of Operations
1. First check IP whitelisting (network policy errors)
2. Then check authentication (JWT/key errors)
3. Finally check user permissions and roles

### 5. Cloud Run Deployment Checklist
- [ ] Static IP reserved via Cloud NAT
- [ ] VPC Connector created and configured
- [ ] Cloud Run service using VPC connector with `--vpc-egress=all-traffic`
- [ ] Snowflake network policy updated with static NAT IP
- [ ] Secrets properly formatted (no trailing newlines)
- [ ] RSA keys match between Snowflake user and GCP secrets
- [ ] Test connection after each change

### 6. Testing Commands
```bash
# Test the deployed service
API_KEY=$(gcloud secrets versions access latest --secret="OPEN_WEBUI_API_KEY" --project=popfly-open-webui 2>/dev/null)
curl -X POST https://snowflake-mcp-server-w7hnua7geq-uc.a.run.app/tools/call \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "list_databases", "arguments": {}}'
```

### 7. Resource Names for This Deployment
- **Static IP**: snowflake-mcp-nat-ip (34.63.149.139)
- **Cloud Router**: snowflake-mcp-router
- **Cloud NAT**: snowflake-mcp-nat
- **VPC Connector**: snowflake-mcp-connector
- **Cloud Run Service**: snowflake-mcp-server
- **Snowflake User**: MCP_POPFLY_SNOWFLAKE
- **Network Policy**: POPFLY_MCP_POLICY

---

## Common Error Messages and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| `Incoming request with IP/Token X.X.X.X is not allowed` | IP not whitelisted in Snowflake | Add IP to network policy or use Cloud NAT |
| `JWT token is invalid` | Wrong private key or formatting issue | Check key matches user, remove trailing newlines |
| `Could not connect to Snowflake backend after 11 attempt(s)` | Network connectivity issue | Check VPC/NAT configuration |
| `SNOWFLAKE_PRIVATE_KEY_PATH: No such file or directory` | Secret contains path not content | Store actual key content in secret |

---

## Custom Domain Setup with SSL Certificate (2025-08-08)

### Setting up Custom Domain for Cloud Run

**Goal:** Make the MCP server accessible at https://mcp.popfly.com

**Process:**

1. **Create domain mapping:**
```bash
gcloud beta run domain-mappings create \
  --service=snowflake-mcp-server \
  --domain=mcp.popfly.com \
  --region=us-central1 \
  --project=popfly-open-webui
```

2. **Configure DNS CNAME record:**
- Record Type: CNAME
- Name/Host: mcp
- Value: ghs.googlehosted.com.
- TTL: 3600

3. **Wait for SSL certificate provisioning:**
- Google automatically provisions a managed SSL certificate
- Can take 15 minutes to 24 hours (typically under 1 hour)
- Check status: `gcloud beta run domain-mappings list --region=us-central1`
- Green checkmark (✔) indicates certificate is ready

**Troubleshooting SSL Issues:**
- If seeing `curl: (35) LibreSSL SSL_connect: SSL_ERROR_SYSCALL`, certificate is still provisioning
- HTTP redirects to HTTPS will work, but HTTPS won't until certificate is ready
- DNS must be properly configured for certificate provisioning to begin

---

## Cloud Run to Cloud Run Authentication Issues (2025-08-08)

### Problem: Open WebUI (ai.popfly.com) Blocked by IP Restrictions

**Symptoms:**
- HTTP 403 Forbidden when ai.popfly.com tried to access MCP server
- Error: "Access denied from IP: 2600:1900:0:2d01::1e01"
- IPv6 addresses kept changing: `2600:1900:0:2d01::1e01`, then `2600:1900:0:2d00::1e01`

**Root Cause:**
- ai.popfly.com (also on Cloud Run) uses dynamic IPv6 addresses
- IP-based authentication was too restrictive for Cloud Run to Cloud Run communication
- IPv6 CIDR range checks weren't working properly

**Failed Attempts:**
1. Added specific IPv6 addresses to allowlist - addresses kept changing
2. Added IPv6 CIDR range `2600:1900::/28` - too narrow
3. Expanded to `2600:1900::/32` - still didn't work properly

**Final Solution: Remove IP Restrictions for API Access**

Created simplified authentication (`auth_middleware/simple_auth.py`):
```python
def validate_auth(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Simple authentication: valid bearer token is sufficient"""
    # Only validate bearer token, no IP restrictions
    # Log request details for monitoring
```

Key changes:
- Removed IP-based restrictions for API endpoints
- Keep bearer token authentication
- Log all requests with IP for monitoring
- Allow any client with valid token to access

**Implementation:**
```bash
# Update server to use simple auth
# Deploy changes
gcloud builds submit --config=cloudbuild.yaml --project=popfly-open-webui
```

---

## Secret Version Management Issues (2025-08-08)

### Problem: Redeployments Reverted to Old Secret Versions

**Symptoms:**
- After multiple redeployments for IP auth fixes, Snowflake authentication broke again
- Error: "JWT token is invalid" returned even though it worked before
- Open WebUI integration showed tools but couldn't execute them

**Root Cause:**
- Cloud Run was configured to use "latest" version of secrets
- Multiple deployments during troubleshooting didn't specify secret versions
- Cloud Run reverted to using version 1 of secrets (which had trailing newlines)

**Detection:**
```bash
# Check which secret versions are being used
gcloud run services describe snowflake-mcp-server \
  --region=us-central1 \
  --project=popfly-open-webui \
  --format="yaml" | grep -B5 -A5 "SNOWFLAKE"

# Verify secret content for trailing newlines
gcloud secrets versions access 1 --secret="SNOWFLAKE_USER" --project=popfly-open-webui | od -c
# Version 1 showed: M C P _ P O P F L Y _ S N O W F L A K E \n (BAD)

gcloud secrets versions access 2 --secret="SNOWFLAKE_USER" --project=popfly-open-webui | od -c  
# Version 2 showed: M C P _ P O P F L Y _ S N O W F L A K E (GOOD - no newline)
```

**Solution: Explicitly Set Secret Versions**
```bash
gcloud run services update snowflake-mcp-server \
  --region=us-central1 \
  --update-secrets=SNOWFLAKE_USER=SNOWFLAKE_USER:2,SNOWFLAKE_PRIVATE_KEY=SNOWFLAKE_PRIVATE_KEY_PATH:4 \
  --project=popfly-open-webui
```

**Prevention:**
- Always explicitly specify secret versions in deployment commands
- Never rely on "latest" for production deployments
- Document which secret versions are correct in deployment scripts

---

## Open WebUI Integration Configuration

### OpenAPI Endpoint Setup

**Issue:** Open WebUI requires an OpenAPI specification URL

**Solution:** FastAPI automatically generates OpenAPI spec at `/openapi.json`

Configuration for Open WebUI:
- **URL:** `https://mcp.popfly.com` (or `https://snowflake-mcp-server-w7hnua7geq-uc.a.run.app`)
- **OpenAPI Path:** `/openapi.json`
- **Auth Type:** Bearer
- **Bearer Token:** [Your configured API key]

---

## Deployment Build Times

**Observation:** Cloud Build times varied significantly
- Normal builds: 3-5 minutes
- During high load: 8-10+ minutes
- Sometimes builds would timeout at 2 minutes in terminal but continue in background

**Best Practice:**
- Use `--async` flag for builds to avoid terminal timeouts
- Monitor build status separately: `gcloud builds list --limit=1 --project=PROJECT_ID`
- Check for new revisions rather than relying on build completion

---

## CORS Configuration

**Updated CORS settings for production:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ai.popfly.com", "https://mcp.popfly.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```
- Restricted from wildcard `["*"]` to specific domains
- Maintains security while allowing authorized services

---

## Key Commands Reference

### Check Service Status
```bash
# View current service configuration
gcloud run services describe snowflake-mcp-server --region=us-central1 --project=popfly-open-webui

# List recent revisions
gcloud run revisions list --service=snowflake-mcp-server --region=us-central1 --limit=5

# Check service logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=snowflake-mcp-server" --limit=20 --project=popfly-open-webui
```

### Secret Management
```bash
# List secret versions
gcloud secrets versions list SECRET_NAME --project=popfly-open-webui

# Check secret content (with special character detection)
gcloud secrets versions access VERSION --secret=SECRET_NAME --project=popfly-open-webui | od -c

# Add new secret version without trailing newline
echo -n "VALUE" | gcloud secrets versions add SECRET_NAME --data-file=- --project=popfly-open-webui
```

### Domain and SSL Management
```bash
# Check domain mapping status
gcloud beta run domain-mappings list --region=us-central1 --project=popfly-open-webui

# Test SSL certificate
curl -I https://mcp.popfly.com/health
```

---

## Future Improvements

1. **Consider using Workload Identity** instead of RSA keys for authentication
2. **Implement secret rotation** mechanism for private keys
3. **Add monitoring** for NAT IP changes (though static IPs shouldn't change)
4. **Document disaster recovery** process if static IP is lost
5. **Consider multi-region deployment** with separate NAT gateways per region
6. **Create deployment script** that explicitly sets correct secret versions
7. **Implement health checks** that verify Snowflake connectivity
8. **Add service-to-service authentication** for Cloud Run services instead of bearer tokens

---

## Migration from Cloud Run to VM-based Deployment (2025-08-11)

### Context
Migrated from container-based Cloud Run deployment to VM-based deployment for MCP server to:
- Simplify deployment and debugging
- Avoid cold starts and container lifecycle issues
- Enable direct SSH access for troubleshooting
- Support stdio-based MCP protocol properly

### New Infrastructure Details
- **GCP Project**: `popfly-mcp-servers` (new dedicated project)
- **VM Instance**: `mcp-snowflake-vm` in `us-central1-a`
- **Machine Type**: `e2-medium`
- **Static IP**: `104.198.62.220`
- **Service Account**: `mcp-snowflake-vm@popfly-mcp-servers.iam.gserviceaccount.com`

### Key Changes Made

1. **Created New GCP Project**
   - Separated MCP services from main application (`popfly-open-webui`)
   - Better resource organization and billing tracking

2. **VM Setup**
   ```bash
   gcloud compute instances create mcp-snowflake-vm \
       --zone=us-central1-a \
       --machine-type=e2-medium \
       --network-interface=network-tier=PREMIUM,subnet=default,address=104.198.62.220 \
       --service-account=mcp-snowflake-vm@popfly-mcp-servers.iam.gserviceaccount.com \
       --scopes=https://www.googleapis.com/auth/cloud-platform
   ```

3. **Updated Snowflake Network Rule**
   - Added new VM IP: `104.198.62.220`
   - Removed old Cloud NAT IP: `34.63.149.139`
   - Current rule: `ALLOW_POPFLY_MCP` contains `('216.16.8.56', '104.198.62.220')`

4. **Secret Management**
   - Secrets now in `popfly-mcp-servers` project
   - Modified `config/settings.py` to load from GCP Secret Manager when `USE_GCP_SECRETS=true`
   - Secrets automatically loaded at runtime, not via environment variables

5. **Deployment Script**
   - Created `deploy_to_vm.sh` for quick deployments
   - Deploys in ~10 seconds via tar archive and SSH

### Cleaned Up Old Infrastructure
- Deleted Cloud Run service `snowflake-mcp-server`
- Deleted VPC Connector `snowflake-mcp-connector`
- Deleted Cloud NAT `snowflake-mcp-nat`
- Deleted Cloud Router `snowflake-mcp-router`
- Deleted Static IP `snowflake-mcp-nat-ip` (34.63.149.139)
- Removed domain mapping for `mcp.popfly.com`
- **Note**: DNS CNAME for `mcp.popfly.com` still points to `ghs.googlehosted.com` - needs removal

### How MCP Server Now Works
1. MCP server runs on-demand via SSH (stdio mode)
2. No longer exposed via HTTP/HTTPS
3. Claude Desktop can connect via:
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
           "--project=popfly-mcp-servers",
           "--command",
           "cd /opt/mcp-snowflake && ./run_mcp.sh"
         ]
       }
     }
   }
   ```

### Files Removed
- `Dockerfile`
- `cloudbuild.yaml`
- `docker-compose.yml`
- `README_HTTP.md`
- `start_http_server.py`

### Benefits of New Approach
- **No cold starts**: VM is always running
- **Direct SSH access**: Easy debugging and log viewing
- **Simpler secrets**: Direct file system access
- **Faster deployments**: 10-second rsync vs multi-minute container builds
- **Better for MCP**: Designed for stdio communication, not HTTP

---

## Enhanced Logging Deployment Issue (2025-08-08)

### Problem: Pre-processing Logs Not Being Created

**Symptoms:**
- Post-processing logs were being created successfully with new columns
- Pre-processing logs were missing entirely or only occasionally appearing
- NULL REQUEST_ID values in many log entries

**Root Cause:**
The enhanced logging code was deployed but pre-processing logs weren't being created because:
1. The `handle_snowflake_tool` and `handle_cortex_tool` functions properly implement pre/post logging
2. However, these are only called from the `/tools/call` endpoint 
3. The `/tools` endpoint (list_tools) was still using the old `log_activity` signature without new parameters
4. Some tools weren't receiving the `request_id` parameter properly, resulting in NULL values

**Investigation Process:**
```sql
-- Check for pre/post entries
SELECT 
    COUNT(*) as COUNT,
    PROCESSING_STAGE,
    ACTION_TYPE
FROM PF.BI.AI_USER_ACTIVITY_LOG
WHERE TIMESTAMP > DATEADD(hour, -1, CURRENT_TIMESTAMP())
  AND ACTION_TYPE = 'tool_execution'
GROUP BY PROCESSING_STAGE, ACTION_TYPE;

-- Result showed:
-- 4 entries with NULL PROCESSING_STAGE (old format)
-- 2 entries with "pre" 
-- 6 entries with "post"
```

**Specific Issues Found:**
1. `list_tools` endpoint wasn't updated to use new logging parameters
2. Some Cortex tool calls had NULL REQUEST_ID
3. The error handling in `log_activity` was silently swallowing exceptions

**Solution:**
Need to ensure ALL endpoints that call `log_activity` are updated with the new signature, and verify that request_id is being properly generated and passed through all code paths.

**Lesson Learned:**
When adding new required parameters to a logging function, must audit ALL call sites to ensure they're updated. Silent error handling in logging functions can mask deployment issues - better to have verbose error logging during deployment validation.