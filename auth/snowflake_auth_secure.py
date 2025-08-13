import snowflake.connector
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key
import os
import tempfile
import logging
from typing import Optional
from google.cloud import secretmanager
from config.settings import settings

def get_secret_from_gcp(secret_name: str, project_id: str) -> str:
    """Get secret from GCP Secret Manager"""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

def get_private_key_from_secret() -> bytes:
    """Get private key bytes from GCP Secret Manager for connection pool"""
    try:
        # Get private key content from settings (which loads from GCP)
        private_key_content = settings.snowflake_private_key
        
        if not private_key_content:
            # Fallback to loading directly from secret manager
            private_key_content = get_secret_from_gcp('SNOWFLAKE_PRIVATE_KEY', settings.gcp_project_id)
        
        # Parse the PEM content and convert to DER format
        private_key = load_pem_private_key(
            private_key_content.encode() if isinstance(private_key_content, str) else private_key_content,
            password=None
        )
        
        # Convert to DER format for Snowflake
        pkb = private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        return pkb
        
    except Exception as e:
        logging.error(f"Failed to get private key from secret: {e}")
        raise

def get_snowflake_connection_secure(
    account: str,
    user: str,
    private_key_secret_name: str,
    project_id: str,
    private_key_passphrase: Optional[str] = None,
    database: Optional[str] = None,
    schema: Optional[str] = None,
    warehouse: Optional[str] = None,
    role: Optional[str] = None
) -> snowflake.connector.SnowflakeConnection:
    """Get authenticated Snowflake connection using RSA private key from GCP Secret Manager"""
    
    try:
        # Get private key from GCP Secret Manager
        private_key_content = get_secret_from_gcp(private_key_secret_name, project_id)
        
        # Create temporary file for private key
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as temp_key_file:
            temp_key_file.write(private_key_content)
            temp_key_path = temp_key_file.name
        
        try:
            # Load private key
            with open(temp_key_path, 'rb') as key_file:
                private_key = load_pem_private_key(
                    key_file.read(),
                    password=private_key_passphrase.encode() if private_key_passphrase else None
                )
            
            pkb = private_key.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            return snowflake.connector.connect(
                account=account,
                user=user,
                private_key=pkb,
                database=database,
                schema=schema,
                warehouse=warehouse,
                role=role
            )
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_key_path):
                os.unlink(temp_key_path)
                
    except Exception as error:
        logging.error(f"Failed to establish secure Snowflake connection: {error}")
        raise