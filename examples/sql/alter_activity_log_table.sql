-- SQL script to add new columns to AI_USER_ACTIVITY_LOG table
-- This adds columns for enhanced logging of MCP server requests

-- Add PROCESSING_STAGE column to indicate pre or post processing
ALTER TABLE PF.BI.AI_USER_ACTIVITY_LOG 
ADD COLUMN IF NOT EXISTS PROCESSING_STAGE VARCHAR(10) COMMENT 'Processing stage: pre (raw request) or post (after processing)';

-- Add RAW_REQUEST column to store verbatim request as received
ALTER TABLE PF.BI.AI_USER_ACTIVITY_LOG 
ADD COLUMN IF NOT EXISTS RAW_REQUEST VARIANT COMMENT 'Raw request as received by MCP server (for pre-processing stage)';

-- Note: EXECUTION_TIME_MS should already exist, but let's ensure it's there
-- ALTER TABLE PF.BI.AI_USER_ACTIVITY_LOG 
-- ADD COLUMN IF NOT EXISTS EXECUTION_TIME_MS NUMBER COMMENT 'Execution time in milliseconds';

-- Add REQUEST_ID column to link pre and post entries for the same request
ALTER TABLE PF.BI.AI_USER_ACTIVITY_LOG 
ADD COLUMN IF NOT EXISTS REQUEST_ID VARCHAR(100) COMMENT 'Unique ID to link pre and post processing entries';

-- Optional: Add index on PROCESSING_STAGE for better query performance
-- CREATE INDEX IF NOT EXISTS IDX_AI_USER_ACTIVITY_LOG_STAGE 
-- ON PF.BI.AI_USER_ACTIVITY_LOG (PROCESSING_STAGE);

-- Optional: Add index on REQUEST_ID for joining pre/post entries
-- CREATE INDEX IF NOT EXISTS IDX_AI_USER_ACTIVITY_LOG_REQUEST 
-- ON PF.BI.AI_USER_ACTIVITY_LOG (REQUEST_ID);

-- Query to verify the new columns
-- DESCRIBE TABLE PF.BI.AI_USER_ACTIVITY_LOG;