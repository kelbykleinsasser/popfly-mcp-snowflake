import os
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Environment
    environment: str = os.getenv('ENVIRONMENT', 'local')
    
    # Snowflake Configuration
    snowflake_account: str = os.getenv('SNOWFLAKE_ACCOUNT', '')
    snowflake_user: str = os.getenv('SNOWFLAKE_USER', '')
    snowflake_private_key_path: str = os.getenv('SNOWFLAKE_PRIVATE_KEY_PATH', '')
    snowflake_private_key: Optional[str] = os.getenv('SNOWFLAKE_PRIVATE_KEY')  # For production secrets
    snowflake_private_key_passphrase: Optional[str] = os.getenv('SNOWFLAKE_PRIVATE_KEY_PASSPHRASE')
    snowflake_database: str = os.getenv('SNOWFLAKE_DATABASE', 'PF')
    snowflake_schema: str = os.getenv('SNOWFLAKE_SCHEMA', 'BI')
    snowflake_warehouse: str = os.getenv('SNOWFLAKE_WAREHOUSE', 'COMPUTE_WH')
    snowflake_role: Optional[str] = os.getenv('SNOWFLAKE_ROLE')
    
    # Open WebUI
    open_webui_api_key: str = os.getenv('OPEN_WEBUI_API_KEY', '')
    
    # Cortex Configuration
    cortex_model: str = os.getenv('CORTEX_MODEL', 'llama3.1-70b')
    cortex_timeout: int = int(os.getenv('CORTEX_TIMEOUT', '30'))
    cortex_max_tokens: int = int(os.getenv('CORTEX_MAX_TOKENS', '3000'))
    
    # Query Configuration
    max_query_rows: int = int(os.getenv('MAX_QUERY_ROWS', '1000'))
    max_query_rows_limit: int = int(os.getenv('MAX_QUERY_ROWS_LIMIT', '10000'))
    query_timeout: int = int(os.getenv('QUERY_TIMEOUT', '30'))
    
    # GCP Configuration
    gcp_project_id: Optional[str] = os.getenv('GCP_PROJECT_ID')
    
    def validate_required_settings(self) -> bool:
        """Validate that all required settings are present"""
        required_base = ['snowflake_account', 'snowflake_user']
        
        if self.environment == 'production':
            # Production: need either private key content or GCP project for secret manager
            if not self.snowflake_private_key and not self.gcp_project_id:
                raise ValueError("Production requires either SNOWFLAKE_PRIVATE_KEY or GCP_PROJECT_ID")
        else:
            # Local: need private key path
            required_base.append('snowflake_private_key_path')
        
        missing = [field for field in required_base if not getattr(self, field)]
        
        if missing:
            raise ValueError(f"Missing required settings: {missing}")
        
        return True

settings = Settings()