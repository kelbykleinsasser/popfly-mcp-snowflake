"""
Snowflake authentication utilities for RSA key pair authentication.
"""
import os
import snowflake.connector
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key

class Config:
    """Simple config class for the example"""
    def __init__(self):
        self.environment = os.getenv('ENVIRONMENT', 'local')
        self.snowflake_user = os.getenv('SNOWFLAKE_USER')
        self.snowflake_account = os.getenv('SNOWFLAKE_ACCOUNT')
        self.snowflake_warehouse = os.getenv('SNOWFLAKE_WAREHOUSE')
        self.snowflake_database = os.getenv('SNOWFLAKE_DATABASE')
        self.snowflake_schema = os.getenv('SNOWFLAKE_SCHEMA')
        self.snowflake_role = os.getenv('SNOWFLAKE_ROLE')
        self.snowflake_private_key_path = os.getenv('SNOWFLAKE_PRIVATE_KEY_PATH')
        self.snowflake_private_key = os.getenv('SNOWFLAKE_PRIVATE_KEY')

config = Config()

def load_private_key():
    """Load the RSA private key from file or GCP Secret Manager."""
    if config.environment == 'production':
        # In production, private key comes from GCP as string
        private_key_str = config.snowflake_private_key
        private_key = load_pem_private_key(
            private_key_str.encode(),
            password=None
        )
    else:
        # In local dev, load from file
        key_path = config.snowflake_private_key_path
        if not os.path.exists(key_path):
            raise FileNotFoundError(f"Private key file not found: {key_path}")
        
        with open(key_path, 'rb') as key_file:
            private_key = load_pem_private_key(
                key_file.read(),
                password=None
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
        user=config.snowflake_user,
        account=config.snowflake_account,
        warehouse=config.snowflake_warehouse,
        database=config.snowflake_database,
        schema=config.snowflake_schema,
        role=config.snowflake_role,
        private_key=private_key_der
    )
    
    return connection
