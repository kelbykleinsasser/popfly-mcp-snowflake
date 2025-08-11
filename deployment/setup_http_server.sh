#!/bin/bash
set -e

# Configuration
VM_NAME="mcp-snowflake-vm"
VM_ZONE="us-central1-a"
PROJECT_ID="popfly-mcp-servers"
DOMAIN="mcp.popfly.com"

echo "🚀 Setting up HTTP server on VM..."

# First deploy the latest code
echo "📦 Deploying latest code..."
./deploy_to_vm.sh

# SSH to VM and set up HTTP server
echo "🔧 Configuring HTTP server on VM..."
gcloud compute ssh $VM_NAME --zone=$VM_ZONE --project=$PROJECT_ID --command="
    # Install nginx and certbot
    sudo apt-get update
    sudo apt-get install -y nginx certbot python3-certbot-nginx
    
    # Stop nginx temporarily
    sudo systemctl stop nginx
    
    # Create systemd service for HTTP server
    sudo tee /etc/systemd/system/mcp-http.service << 'EOF'
[Unit]
Description=MCP Snowflake HTTP Server
After=network.target

[Service]
Type=simple
User=\$USER
WorkingDirectory=/opt/mcp-snowflake
Environment=\"PATH=/opt/mcp-snowflake/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\"
Environment=\"USE_GCP_SECRETS=true\"
Environment=\"GCP_PROJECT_ID=popfly-mcp-servers\"
Environment=\"ENVIRONMENT=production\"
Environment=\"SNOWFLAKE_DATABASE=PF\"
Environment=\"SNOWFLAKE_SCHEMA=BI\"
Environment=\"SNOWFLAKE_WAREHOUSE=COMPUTE_WH\"
Environment=\"SNOWFLAKE_ROLE=MCP_ROLE\"
ExecStart=/opt/mcp-snowflake/venv/bin/python -m uvicorn server.mcp_server_http:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    # Create nginx configuration
    sudo tee /etc/nginx/sites-available/mcp-snowflake << 'EOF'
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \\\$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \\\$host;
        proxy_cache_bypass \\\$http_upgrade;
        proxy_set_header X-Real-IP \\\$remote_addr;
        proxy_set_header X-Forwarded-For \\\$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \\\$scheme;
    }
}
EOF

    # Enable the site
    sudo ln -sf /etc/nginx/sites-available/mcp-snowflake /etc/nginx/sites-enabled/
    sudo rm -f /etc/nginx/sites-enabled/default
    
    # Start services
    sudo systemctl daemon-reload
    sudo systemctl enable mcp-http
    sudo systemctl start mcp-http
    sudo systemctl start nginx
    
    # Get SSL certificate (this will modify nginx config automatically)
    sudo certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email kelby@popfly.com --redirect
    
    # Restart nginx with SSL
    sudo systemctl reload nginx
    
    echo '✅ HTTP server setup complete!'
"

echo ""
echo "✅ Setup complete!"
echo ""
echo "📝 Next steps:"
echo "1. Update DNS record for $DOMAIN to point to: 104.198.62.220"
echo "2. Wait a few minutes for DNS propagation"
echo "3. Test: curl https://$DOMAIN/health"
echo ""
echo "To view logs:"
echo "gcloud compute ssh $VM_NAME --zone=$VM_ZONE --project=$PROJECT_ID --command='sudo journalctl -u mcp-http -f'"