from functools import wraps
from typing import Optional
import os

def verify_bearer_token(authorization_header: Optional[str]) -> bool:
    """Verify the bearer token from Open WebUI"""
    if not authorization_header:
        return False
    
    try:
        scheme, token = authorization_header.split()
        if scheme.lower() != 'bearer':
            return False
        
        # In production, validate against stored tokens or Open WebUI's API
        expected_token = os.getenv('OPEN_WEBUI_API_KEY')
        return token == expected_token
    except:
        return False

def require_auth(f):
    """Decorator to require Open WebUI authentication"""
    @wraps(f)
    async def decorated_function(request, *args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not verify_bearer_token(auth_header):
            return {"error": "Unauthorized"}, 401
        return await f(request, *args, **kwargs)
    return decorated_function
