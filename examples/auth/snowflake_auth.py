"""
Snowflake authentication utilities for RSA key pair authentication.
"""
import os
import snowflake.connector
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from dotenv import load_dotenv

load_dotenv()

def load_private_key():
    """Load the RSA private key from file for Snowflake authentication."""
    key_path = os.getenv('SNOWFLAKE_PRIVATE_KEY_PATH', os.path.join(os.path.dirname(__file__), 'snowflake_key.pem'))
    
    if not os.path.exists(key_path):
        raise FileNotFoundError(f"Private key file not found: {key_path}")
    
    with open(key_path, 'rb') as key_file:
        private_key = load_pem_private_key(
            key_file.read(),
            password=None  # No passphrase for our key
        )
    
    return private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

def get_snowflake_connection():
    """Create a Snowflake connection using RSA key pair authentication."""
    private_key_der = load_private_key()
    
    connection = snowflake.connector.connect(
        user=os.getenv('SNOWFLAKE_USER', 'TRANSFORMATIONS_SERVICE'),
        account=os.getenv('SNOWFLAKE_ACCOUNT'),
        warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
        database=os.getenv('SNOWFLAKE_DATABASE'),
        schema=os.getenv('SNOWFLAKE_SCHEMA'),
        role=os.getenv('SNOWFLAKE_ROLE'),
        private_key=private_key_der
    )
    
    return connection