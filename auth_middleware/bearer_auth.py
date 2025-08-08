from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config.settings import settings
import logging

security = HTTPBearer()

def validate_bearer_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Validate bearer token from Open WebUI"""
    expected_token = settings.open_webui_api_key
    
    if not expected_token:
        logging.error("OPEN_WEBUI_API_KEY not configured")
        raise HTTPException(status_code=500, detail="Server configuration error")
    
    # Strip any whitespace from both tokens
    provided_token = credentials.credentials.strip()
    expected_token = expected_token.strip()
    
    if provided_token != expected_token:
        logging.warning(f"Invalid bearer token attempt. Provided: {provided_token[:10]}... Expected: {expected_token[:10]}...")
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    
    return provided_token