"""
Secure Snowflake authentication using Google Secret Manager
"""
import os
import snowflake.connector
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from .secret_manager import get_secret_manager

def get_snowflake_connection():
    """Get Snowflake connection using secrets from Secret Manager"""
    sm = get_secret_manager()
    config = sm.get_snowflake_config()
    
    # Get private key from secret manager
    private_key_path = sm.get_snowflake_private_key_path()
    
    try:
        # Load private key
        with open(private_key_path, "rb") as key_file:
            private_key = serialization.load_pem_private_key(
                key_file.read(),
                password=None,
                backend=default_backend()
            )
        
        # Convert to DER format for Snowflake
        private_key_der = private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        # Create connection
        conn = snowflake.connector.connect(
            account=config["account"],
            user=config["user"],
            private_key=private_key_der,
            database=config["database"],
            schema=config["schema"],
            warehouse=config["warehouse"],
            role=config["role"]
        )
        
        return conn
        
    finally:
        # Clean up temporary key file
        if private_key_path and os.path.exists(private_key_path):
            os.remove(private_key_path)