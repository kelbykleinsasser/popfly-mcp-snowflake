import snowflake.connector
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key
import os
import tempfile
from typing import Optional

def get_snowflake_connection(
    account: str,
    user: str,
    private_key_path: str,
    private_key_passphrase: Optional[str] = None,
    database: Optional[str] = None,
    schema: Optional[str] = None,
    warehouse: Optional[str] = None,
    role: Optional[str] = None
) -> snowflake.connector.SnowflakeConnection:
    """Get authenticated Snowflake connection using RSA private key"""
    
    # Resolve absolute path to handle relative paths correctly
    if not os.path.isabs(private_key_path):
        # If relative path, resolve relative to project root
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        private_key_path = os.path.join(project_root, private_key_path)
    
    private_key_path = os.path.abspath(private_key_path)
    
    with open(private_key_path, 'rb') as key_file:
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


def get_snowflake_connection_from_content(
    account: str,
    user: str,
    private_key_content: str,
    private_key_passphrase: Optional[str] = None,
    database: Optional[str] = None,
    schema: Optional[str] = None,
    warehouse: Optional[str] = None,
    role: Optional[str] = None
) -> snowflake.connector.SnowflakeConnection:
    """Get authenticated Snowflake connection using RSA private key content"""
    
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
        os.unlink(temp_key_path)