#!/bin/bash
set -e

# Configuration
VM_NAME="mcp-snowflake-vm"
VM_ZONE="us-central1-a"
REMOTE_DIR="/opt/mcp-snowflake"
LOCAL_DIR="."
PROJECT_ID="popfly-mcp-servers"

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
    --exclude='.DS_Store' \
    --exclude='Dockerfile' \
    --exclude='cloudbuild.yaml' \
    --exclude='docker-compose.yml' \
    .

# First SSH to create directory and install dependencies
echo "🔧 Setting up VM environment..."
gcloud compute ssh $VM_NAME --zone=$VM_ZONE --project=$PROJECT_ID --command="
    sudo apt-get update && \
    sudo apt-get install -y python3.11 python3.11-venv python3-pip git && \
    sudo mkdir -p $REMOTE_DIR && \
    sudo chown \$USER:\$USER $REMOTE_DIR
"

# Copy to VM
echo "📤 Uploading to VM..."
gcloud compute scp /tmp/mcp-deployment.tar.gz \
    $VM_NAME:/tmp/mcp-deployment.tar.gz \
    --zone=$VM_ZONE \
    --project=$PROJECT_ID

# Extract and setup Python environment
echo "🔄 Extracting and setting up Python environment..."
gcloud compute ssh $VM_NAME --zone=$VM_ZONE --project=$PROJECT_ID --command="
    cd $REMOTE_DIR && \
    tar -xzf /tmp/mcp-deployment.tar.gz && \
    python3.11 -m venv venv && \
    source venv/bin/activate && \
    pip install --upgrade pip && \
    pip install -r requirements.txt
"

# Cleanup
rm /tmp/mcp-deployment.tar.gz

echo "✅ MCP server code deployed to VM!"
echo ""
echo "Next steps:"
echo "1. SSH into VM: gcloud compute ssh $VM_NAME --zone=$VM_ZONE --project=$PROJECT_ID"
echo "2. Set up environment variables and secrets"
echo "3. Configure and start the systemd service"