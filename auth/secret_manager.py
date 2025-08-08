import os
import logging
from typing import Optional, Dict, Any
from google.cloud import secretmanager
from pydantic import BaseModel

class SnowflakeConfig(BaseModel):
    """Snowflake connection configuration"""
    account: str
    user: str
    private_key_path: Optional[str] = None
    private_key_secret_name: Optional[str] = None
    private_key_passphrase: Optional[str] = None
    database: Optional[str] = None
    schema: Optional[str] = None
    warehouse: Optional[str] = None
    role: Optional[str] = None

class SecretManager:
    """Centralized secret management for local and GCP environments"""
    
    def __init__(self, project_id: Optional[str] = None):
        self.project_id = project_id
        self.client = None
        
        if project_id:
            try:
                self.client = secretmanager.SecretManagerServiceClient()
            except Exception as error:
                logging.warning(f"Failed to initialize GCP Secret Manager client: {error}")
    
    def get_secret(self, secret_name: str, default_env_var: Optional[str] = None) -> Optional[str]:
        """Get secret from GCP Secret Manager or fallback to environment variable"""
        
        # Try GCP Secret Manager first (if available)
        if self.client and self.project_id:
            try:
                name = f"projects/{self.project_id}/secrets/{secret_name}/versions/latest"
                response = self.client.access_secret_version(request={"name": name})
                return response.payload.data.decode("UTF-8")
            except Exception as error:
                logging.warning(f"Failed to get secret {secret_name} from GCP: {error}")
        
        # Fallback to environment variable
        if default_env_var:
            return os.getenv(default_env_var)
        
        return os.getenv(secret_name)
    
    def get_snowflake_config(self) -> SnowflakeConfig:
        """Get complete Snowflake configuration from secrets/environment"""
        
        return SnowflakeConfig(
            account=self.get_secret("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_ACCOUNT"),
            user=self.get_secret("SNOWFLAKE_USER", "SNOWFLAKE_USER"),
            private_key_path=self.get_secret("SNOWFLAKE_PRIVATE_KEY_PATH", "SNOWFLAKE_PRIVATE_KEY_PATH"),
            private_key_secret_name=self.get_secret("SNOWFLAKE_PRIVATE_KEY_SECRET"),
            private_key_passphrase=self.get_secret("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE", "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE"),
            database=self.get_secret("SNOWFLAKE_DATABASE", "SNOWFLAKE_DATABASE"),
            schema=self.get_secret("SNOWFLAKE_SCHEMA", "SNOWFLAKE_SCHEMA"),
            warehouse=self.get_secret("SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_WAREHOUSE"),
            role=self.get_secret("SNOWFLAKE_ROLE", "SNOWFLAKE_ROLE")
        )