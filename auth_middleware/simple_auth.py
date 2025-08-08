"""Simplified authentication middleware for MCP server"""
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config.settings import settings
import logging
from typing import Optional

security = HTTPBearer()

# Allowed IP addresses for direct access
ALLOWED_IPS = [
    "84.46.140.216",  # Personal static IP 1
    "216.16.8.56",    # Personal static IP 2
]

def get_client_ip(request: Request) -> str:
    """Extract the real client IP from the request"""
    # Check for X-Forwarded-For header (set by Cloud Run/Load Balancer)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain (original client)
        return forwarded_for.split(",")[0].strip()
    
    # Check for X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    # Fallback to direct client IP
    if request.client:
        return request.client.host
    return "unknown"

def validate_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Simple authentication: valid bearer token is sufficient"""
    
    # Validate the bearer token
    expected_token = settings.open_webui_api_key
    
    if not expected_token:
        logging.error("OPEN_WEBUI_API_KEY not configured")
        raise HTTPException(status_code=500, detail="Server configuration error")
    
    provided_token = credentials.credentials.strip()
    expected_token = expected_token.strip()
    
    if provided_token != expected_token:
        client_ip = get_client_ip(request)
        logging.warning(f"Invalid bearer token attempt from IP {client_ip}")
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    
    # Log successful auth
    client_ip = get_client_ip(request)
    origin = request.headers.get("Origin", "")
    referer = request.headers.get("Referer", "")
    user_agent = request.headers.get("User-Agent", "")
    
    logging.info(f"Authenticated request from IP: {client_ip}, Origin: {origin}, Referer: {referer}, UA: {user_agent[:50]}")
    
    return provided_token

def validate_auth_with_ip(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Authentication with IP restrictions (only for admin endpoints)"""
    
    # First validate the bearer token
    token = validate_auth(request, credentials)
    
    # Then check IP for admin operations
    client_ip = get_client_ip(request)
    
    if client_ip not in ALLOWED_IPS:
        logging.warning(f"Admin access denied for IP: {client_ip}")
        raise HTTPException(
            status_code=403, 
            detail=f"Admin access denied from IP: {client_ip}"
        )
    
    return token