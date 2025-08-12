import os
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Environment
    environment: str = os.getenv('ENVIRONMENT', 'local')
    
    # GCP Configuration
    gcp_project_id: Optional[str] = os.getenv('GCP_PROJECT_ID')
    use_gcp_secrets: bool = os.getenv('USE_GCP_SECRETS', 'false').lower() == 'true'
    
    # Initialize with defaults
    snowflake_account: str = ''
    snowflake_user: str = ''
    snowflake_private_key_path: str = ''
    snowflake_private_key: Optional[str] = None
    snowflake_private_key_passphrase: Optional[str] = None
    snowflake_database: str = 'PF'
    snowflake_schema: str = 'BI'
    snowflake_warehouse: str = 'COMPUTE_WH'
    snowflake_role: Optional[str] = None
    open_webui_api_key: str = ''
    
    # Cortex Configuration
    cortex_model: str = 'llama3.1-70b'  # Back to 70b - it's actually faster than 8b
    cortex_timeout: int = 30
    cortex_max_tokens: int = 3000
    cortex_intelligent_filtering: bool = True  # Filter columns based on query relevance (disable if less reliable)
    cortex_prewarm_on_startup: bool = True  # Pre-warm Cortex on startup to avoid cold starts
    cortex_use_search: bool = True  # Use Cortex Search for context (90% prompt reduction)
    
    # Query Configuration
    max_query_rows: int = 1000
    max_query_rows_limit: int = 10000
    query_timeout: int = 30
    
    # Connection Pool Configuration
    connection_pool_min_size: int = 2
    connection_pool_max_size: int = 10
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        if self.use_gcp_secrets and self.gcp_project_id:
            # Load from GCP Secret Manager
            self._load_from_gcp_secrets()
        else:
            # Load from environment variables
            self._load_from_env()
    
    def _load_from_gcp_secrets(self):
        """Load configuration from GCP Secret Manager"""
        try:
            from google.cloud import secretmanager
            client = secretmanager.SecretManagerServiceClient()
            
            def get_secret(name: str, default: str = '') -> str:
                try:
                    secret_name = f"projects/{self.gcp_project_id}/secrets/{name}/versions/latest"
                    response = client.access_secret_version(request={"name": secret_name})
                    return response.payload.data.decode("UTF-8").strip()
                except Exception:
                    return default
            
            # Load secrets from GCP
            self.snowflake_account = get_secret('SNOWFLAKE_ACCOUNT') or os.getenv('SNOWFLAKE_ACCOUNT', '')
            self.snowflake_user = get_secret('SNOWFLAKE_USER') or os.getenv('SNOWFLAKE_USER', '')
            self.snowflake_private_key = get_secret('SNOWFLAKE_PRIVATE_KEY')
            self.snowflake_database = get_secret('SNOWFLAKE_DATABASE') or os.getenv('SNOWFLAKE_DATABASE', 'PF')
            self.snowflake_schema = get_secret('SNOWFLAKE_SCHEMA') or os.getenv('SNOWFLAKE_SCHEMA', 'BI')
            self.snowflake_warehouse = get_secret('SNOWFLAKE_WAREHOUSE') or os.getenv('SNOWFLAKE_WAREHOUSE', 'COMPUTE_WH')
            self.snowflake_role = get_secret('SNOWFLAKE_ROLE') or os.getenv('SNOWFLAKE_ROLE')
            self.open_webui_api_key = get_secret('OPEN_WEBUI_API_KEY') or os.getenv('OPEN_WEBUI_API_KEY', '')
            
        except ImportError:
            raise ImportError("google-cloud-secret-manager is required for GCP secrets")
    
    def _load_from_env(self):
        """Load configuration from environment variables"""
        self.snowflake_account = os.getenv('SNOWFLAKE_ACCOUNT', '')
        self.snowflake_user = os.getenv('SNOWFLAKE_USER', '')
        self.snowflake_private_key_path = os.getenv('SNOWFLAKE_PRIVATE_KEY_PATH', '')
        self.snowflake_private_key = os.getenv('SNOWFLAKE_PRIVATE_KEY')
        self.snowflake_private_key_passphrase = os.getenv('SNOWFLAKE_PRIVATE_KEY_PASSPHRASE')
        self.snowflake_database = os.getenv('SNOWFLAKE_DATABASE', 'PF')
        self.snowflake_schema = os.getenv('SNOWFLAKE_SCHEMA', 'BI')
        self.snowflake_warehouse = os.getenv('SNOWFLAKE_WAREHOUSE', 'COMPUTE_WH')
        self.snowflake_role = os.getenv('SNOWFLAKE_ROLE')
        self.open_webui_api_key = os.getenv('OPEN_WEBUI_API_KEY', '')
        
        # Cortex and Query settings
        self.cortex_model = os.getenv('CORTEX_MODEL', 'llama3.1-70b')  # Back to 70b
        self.cortex_timeout = int(os.getenv('CORTEX_TIMEOUT', '30'))
        self.cortex_max_tokens = int(os.getenv('CORTEX_MAX_TOKENS', '3000'))
        self.cortex_intelligent_filtering = os.getenv('CORTEX_INTELLIGENT_FILTERING', 'true').lower() == 'true'
        self.cortex_prewarm_on_startup = os.getenv('CORTEX_PREWARM_ON_STARTUP', 'true').lower() == 'true'
        self.cortex_use_search = os.getenv('CORTEX_USE_SEARCH', 'true').lower() == 'true'
        self.max_query_rows = int(os.getenv('MAX_QUERY_ROWS', '1000'))
        self.max_query_rows_limit = int(os.getenv('MAX_QUERY_ROWS_LIMIT', '10000'))
        self.query_timeout = int(os.getenv('QUERY_TIMEOUT', '30'))
        
        # Connection Pool settings
        self.connection_pool_min_size = int(os.getenv('CONNECTION_POOL_MIN_SIZE', '2'))
        self.connection_pool_max_size = int(os.getenv('CONNECTION_POOL_MAX_SIZE', '10'))
    
    def validate_required_settings(self) -> bool:
        """Validate that all required settings are present"""
        required_base = ['snowflake_account', 'snowflake_user']
        
        if self.environment == 'production' or self.use_gcp_secrets:
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