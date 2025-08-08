import os
from google.cloud import secretmanager

class Config:
    def __init__(self):
        self.environment = os.getenv('ENVIRONMENT', 'local')
        
        if self.environment == 'production':
            self._load_from_gcp_secrets()
        else:
            self._load_from_env()
    
    def _load_from_env(self):
        """Load configuration from .env file (local development)"""
        from dotenv import load_dotenv
        load_dotenv()
        
        self.snowflake_user = os.getenv('SNOWFLAKE_USER')
        self.snowflake_account = os.getenv('SNOWFLAKE_ACCOUNT')
        self.snowflake_private_key_path = os.getenv('SNOWFLAKE_PRIVATE_KEY_PATH')
        self.open_webui_api_key = os.getenv('OPEN_WEBUI_API_KEY')
        
    def _load_from_gcp_secrets(self):
        """Load configuration from GCP Secret Manager (production)"""
        client = secretmanager.SecretManagerServiceClient()
        project_id = os.getenv('GCP_PROJECT_ID')
        
        # Helper to get secret
        def get_secret(secret_id):
            name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
            response = client.access_secret_version(request={"name": name})
            return response.payload.data.decode("UTF-8")
        
        self.snowflake_user = get_secret('snowflake-user')
        self.snowflake_account = get_secret('snowflake-account')
        self.snowflake_private_key = get_secret('snowflake-private-key')
        self.open_webui_api_key = get_secret('open-webui-api-key')
