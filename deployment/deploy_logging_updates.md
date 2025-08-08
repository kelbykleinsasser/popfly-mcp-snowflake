# Deployment Guide: Enhanced Logging System (2025-08-08)

## Overview
This deployment adds enhanced logging capabilities to capture raw MCP requests and execution timing.

## Changes Being Deployed
1. New columns in AI_USER_ACTIVITY_LOG table
2. Updated logging function to use new columns
3. Request ID linking for pre/post processing entries
4. Execution time tracking

## Step 1: Apply Database Changes

Run the following SQL in Snowflake production (PF.BI schema):

```sql
-- Add PROCESSING_STAGE column to indicate pre or post processing
ALTER TABLE PF.BI.AI_USER_ACTIVITY_LOG 
ADD COLUMN IF NOT EXISTS PROCESSING_STAGE VARCHAR(10) COMMENT 'Processing stage: pre (raw request) or post (after processing)';

-- Add RAW_REQUEST column to store verbatim request as received
ALTER TABLE PF.BI.AI_USER_ACTIVITY_LOG 
ADD COLUMN IF NOT EXISTS RAW_REQUEST VARIANT COMMENT 'Raw request as received by MCP server (for pre-processing stage)';

-- Add REQUEST_ID column to link pre and post entries for the same request
ALTER TABLE PF.BI.AI_USER_ACTIVITY_LOG 
ADD COLUMN IF NOT EXISTS REQUEST_ID VARCHAR(100) COMMENT 'Unique ID to link pre and post processing entries';

-- Verify the new columns were added
DESCRIBE TABLE PF.BI.AI_USER_ACTIVITY_LOG;
```

## Step 2: Deploy Code Updates

Build and deploy the updated code to Cloud Run:

```bash
# From the project root directory
cd /Users/kelbyk/Dev/Popfly/popfly-mcp-snowflake

# Submit build to Cloud Build
gcloud builds submit --config=cloudbuild.yaml --project=popfly-open-webui

# Monitor build progress
gcloud builds list --limit=1 --project=popfly-open-webui --format="table(id,status,createTime)"
```

## Step 3: Verify Deployment

### Check Service Status
```bash
# View current revision
gcloud run services describe snowflake-mcp-server \
  --region=us-central1 \
  --project=popfly-open-webui \
  --format="value(status.latestReadyRevisionName)"

# Check recent logs for any errors
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=snowflake-mcp-server AND severity>=ERROR" \
  --limit=10 \
  --project=popfly-open-webui \
  --format="table(timestamp,textPayload)"
```

### Test the Deployment
```bash
# Get API key from secrets
API_KEY=$(gcloud secrets versions access 2 --secret="OPEN_WEBUI_API_KEY" --project=popfly-open-webui 2>/dev/null)

# Test list_databases endpoint
curl -X POST https://mcp.popfly.com/tools/call \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "list_databases", "arguments": {}}' | jq .
```

## Step 4: Verify Logging

Check that new log entries are being created with the new columns:

```sql
-- Check for recent entries with new columns
SELECT 
    REQUEST_ID,
    PROCESSING_STAGE,
    ACTION_TYPE,
    ENTITY_ID,
    EXECUTION_TIME_MS,
    RAW_REQUEST,
    CREATED_AT
FROM PF.BI.AI_USER_ACTIVITY_LOG
WHERE CREATED_AT > DATEADD(hour, -1, CURRENT_TIMESTAMP())
  AND REQUEST_ID IS NOT NULL
ORDER BY CREATED_AT DESC
LIMIT 20;

-- Verify pre/post pairs
SELECT 
    REQUEST_ID,
    COUNT(*) as entry_count,
    LISTAGG(PROCESSING_STAGE, ', ') as stages,
    MAX(EXECUTION_TIME_MS) as execution_time
FROM PF.BI.AI_USER_ACTIVITY_LOG
WHERE REQUEST_ID IS NOT NULL
GROUP BY REQUEST_ID
HAVING COUNT(*) = 2
ORDER BY MAX(CREATED_AT) DESC
LIMIT 10;
```

## Rollback Plan

If issues occur, rollback by:

1. Reverting to previous Cloud Run revision:
```bash
# List recent revisions
gcloud run revisions list \
  --service=snowflake-mcp-server \
  --region=us-central1 \
  --limit=5 \
  --project=popfly-open-webui

# Rollback to previous revision (replace REVISION_NAME)
gcloud run services update-traffic snowflake-mcp-server \
  --to-revisions=REVISION_NAME=100 \
  --region=us-central1 \
  --project=popfly-open-webui
```

2. The database changes are backward compatible (new columns with NULL allowed), so no DB rollback needed.

## Post-Deployment Monitoring

Monitor for 30 minutes after deployment:

```bash
# Watch for errors
watch -n 60 'gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=snowflake-mcp-server AND severity>=ERROR" --limit=5 --project=popfly-open-webui --format="table(timestamp,textPayload)"'

# Check request rate
gcloud monitoring read \
  "resource.type=\"cloud_run_revision\" AND metric.type=\"run.googleapis.com/request_count\"" \
  --project=popfly-open-webui \
  --format="table(points.value,points.interval.endTime)" \
  --limit=10
```

## Expected Behavior After Deployment

1. Each MCP tool call will create TWO log entries:
   - One "pre" entry with raw_request and REQUEST_ID
   - One "post" entry with execution_time_ms and same REQUEST_ID

2. ACTION_TYPE will be simplified to "tool_execution" for both
3. PROCESSING_STAGE column will contain "pre" or "post"
4. RAW_REQUEST will contain the verbatim JSON request (for pre entries only)
5. EXECUTION_TIME_MS will be populated for post entries

## Notes

- Based on deployment lessons, remember to use explicit secret versions (currently using version 2 for SNOWFLAKE_USER and version 4 for SNOWFLAKE_PRIVATE_KEY_PATH)
- Static NAT IP (34.63.149.139) should remain configured
- VPC connector (snowflake-mcp-connector) should be active
- Build typically takes 3-5 minutes but can take up to 10 minutes during high load