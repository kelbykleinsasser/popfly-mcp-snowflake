import os
import logging
from typing import Optional
from auth.snowflake_auth import get_snowflake_connection, get_snowflake_connection_from_content
from auth.snowflake_auth_secure import get_snowflake_connection_secure
from auth.secret_manager import SecretManager
from config.settings import settings

def get_environment_snowflake_connection():
    """Get Snowflake connection based on environment configuration"""
    
    if settings.environment == 'production':
        # Production: Use environment variables (Cloud Run secrets)
        if settings.snowflake_private_key:
            # Direct private key from environment variable
            return get_snowflake_connection_from_content(
                account=settings.snowflake_account,
                user=settings.snowflake_user,
                private_key_content=settings.snowflake_private_key,
                private_key_passphrase=settings.snowflake_private_key_passphrase,
                database=settings.snowflake_database,
                schema=settings.snowflake_schema,
                warehouse=settings.snowflake_warehouse,
                role=settings.snowflake_role
            )
        elif settings.gcp_project_id:
            # Fallback to GCP Secret Manager
            return get_snowflake_connection_secure(
                account=settings.snowflake_account,
                user=settings.snowflake_user,
                private_key_secret_name='SNOWFLAKE_PRIVATE_KEY',
                project_id=settings.gcp_project_id,
                private_key_passphrase=settings.snowflake_private_key_passphrase,
                database=settings.snowflake_database,
                schema=settings.snowflake_schema,
                warehouse=settings.snowflake_warehouse,
                role=settings.snowflake_role
            )
        else:
            raise ValueError("Production environment requires either SNOWFLAKE_PRIVATE_KEY or GCP_PROJECT_ID")
    else:
        # Local: Use file-based authentication
        return get_snowflake_connection(
            account=settings.snowflake_account,
            user=settings.snowflake_user,
            private_key_path=settings.snowflake_private_key_path,
            private_key_passphrase=settings.snowflake_private_key_passphrase,
            database=settings.snowflake_database,
            schema=settings.snowflake_schema,
            warehouse=settings.snowflake_warehouse,
            role=settings.snowflake_role
        )

def setup_logging():
    """Setup logging configuration based on environment"""
    level = logging.DEBUG if settings.environment == 'local' else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('mcp_server.log') if settings.environment == 'production' else logging.NullHandler()
        ]
    )