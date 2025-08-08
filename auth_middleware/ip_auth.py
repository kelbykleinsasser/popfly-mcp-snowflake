"""IP-based access control middleware for MCP server"""
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config.settings import settings
import logging
from typing import List, Optional

security = HTTPBearer()

# Allowed IP addresses
ALLOWED_IPS = [
    "84.46.140.216",  # Personal static IP 1
    "216.16.8.56",    # Personal static IP 2
]

# Cloud Run services communicate via internal Google networks
# These are Google's internal IP ranges that Cloud Run uses
GOOGLE_INTERNAL_RANGES = [
    "10.0.0.0/8",      # Private network range
    "172.16.0.0/12",   # Private network range  
    "192.168.0.0/16",  # Private network range
    "169.254.0.0/16",  # Link-local
    "35.0.0.0/8",      # Google Cloud ranges
    "34.0.0.0/8",      # Google Cloud ranges
    "2600:1900::/32",  # Google Cloud IPv6 range (broader to cover dynamic IPs)
]

def is_ip_in_range(ip: str, cidr: str) -> bool:
    """Check if an IP address is within a CIDR range"""
    import ipaddress
    try:
        return ipaddress.ip_address(ip) in ipaddress.ip_network(cidr)
    except ValueError:
        return False

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
    return request.client.host

def validate_ip_and_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Validate both IP address and bearer token"""
    
    # First validate the bearer token
    expected_token = settings.open_webui_api_key
    
    if not expected_token:
        logging.error("OPEN_WEBUI_API_KEY not configured")
        raise HTTPException(status_code=500, detail="Server configuration error")
    
    provided_token = credentials.credentials.strip()
    expected_token = expected_token.strip()
    
    if provided_token != expected_token:
        logging.warning(f"Invalid bearer token attempt from IP {get_client_ip(request)}")
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    
    # Then validate the IP address
    client_ip = get_client_ip(request)
    logging.info(f"Request from IP: {client_ip}")
    
    # Check if IP is in allowed list
    if client_ip in ALLOWED_IPS:
        logging.info(f"Allowed IP: {client_ip}")
        return provided_token
    
    # Check if it's from Google's internal network (Cloud Run to Cloud Run)
    for cidr in GOOGLE_INTERNAL_RANGES:
        if is_ip_in_range(client_ip, cidr):
            logging.info(f"Request from Google internal network: {client_ip}")
            # For internal Google traffic, check for specific headers
            user_agent = request.headers.get("User-Agent", "")
            if "Google" in user_agent or "CloudRun" in user_agent:
                return provided_token
    
    # Check if request is from ai.popfly.com by checking the referer or origin
    origin = request.headers.get("Origin", "")
    referer = request.headers.get("Referer", "")
    
    if "ai.popfly.com" in origin or "ai.popfly.com" in referer:
        logging.info(f"Request from ai.popfly.com (origin/referer), IP: {client_ip}")
        return provided_token
    
    # If none of the conditions are met, deny access
    logging.warning(f"Access denied for IP: {client_ip}, Origin: {origin}, Referer: {referer}")
    raise HTTPException(
        status_code=403, 
        detail=f"Access denied from IP: {client_ip}. Only allowed from specific IPs or ai.popfly.com"
    )

# Keep the original function for backward compatibility
def validate_bearer_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Validate bearer token from Open WebUI (backward compatibility)"""
    expected_token = settings.open_webui_api_key
    
    if not expected_token:
        logging.error("OPEN_WEBUI_API_KEY not configured")
        raise HTTPException(status_code=500, detail="Server configuration error")
    
    provided_token = credentials.credentials.strip()
    expected_token = expected_token.strip()
    
    if provided_token != expected_token:
        logging.warning(f"Invalid bearer token attempt")
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    
    return provided_token