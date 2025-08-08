"""
Google Secret Manager integration for secure credential access
"""
import os
import json
import tempfile
from functools import lru_cache
from google.cloud import secretmanager
from google.auth.exceptions import DefaultCredentialsError
import google.auth

class SecretManager:
    """Wrapper for Google Secret Manager with fallback to local .env"""
    
    def __init__(self, project_id=None):
        self.project_id = project_id
        self.client = None
        self.use_local = os.getenv("USE_LOCAL_SECRETS", "false").lower() == "true"
        
        if not self.use_local:
            try:
                if not self.project_id:
                    _, self.project_id = google.auth.default()
                self.client = secretmanager.SecretManagerServiceClient()
            except (DefaultCredentialsError, Exception) as e:
                print(f"Warning: Could not initialize Secret Manager client: {e}")
                print("Falling back to local .env file")
                self.use_local = True
    
    @lru_cache(maxsize=128)
    def get_secret(self, secret_id, version="latest"):
        """Get a secret value from Secret Manager or local .env"""
        if self.use_local:
            # Fallback to environment variables
            return os.getenv(secret_id.upper().replace("-", "_"))
        
        try:
            name = f"projects/{self.project_id}/secrets/{secret_id}/versions/{version}"
            response = self.client.access_secret_version(request={"name": name})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            print(f"Error accessing secret {secret_id}: {e}")
            # Fallback to environment variable
            return os.getenv(secret_id.upper().replace("-", "_"))
    
    def get_secret_as_file(self, secret_id, version="latest"):
        """Get a secret and write it to a temporary file"""
        secret_value = self.get_secret(secret_id, version)
        if not secret_value:
            return None
        
        # Create temporary file
        fd, path = tempfile.mkstemp()
        try:
            with os.fdopen(fd, 'w') as tmp:
                tmp.write(secret_value)
            return path
        except Exception:
            os.remove(path)
            raise
    
    def get_snowflake_config(self):
        """Get Snowflake configuration from secrets"""
        return {
            "account": self.get_secret("snowflake-account"),
            "user": self.get_secret("snowflake-user"),
            "database": self.get_secret("snowflake-database"),
            "schema": self.get_secret("snowflake-schema"),
            "warehouse": self.get_secret("snowflake-warehouse"),
            "role": self.get_secret("snowflake-role"),
        }
    
    def get_snowflake_private_key_path(self):
        """Get Snowflake private key as a temporary file"""
        return self.get_secret_as_file("snowflake-private-key")
    
    def get_google_service_account_path(self):
        """Get Google service account JSON as a temporary file"""
        return self.get_secret_as_file("google-service-account")
    
    def get_slack_config(self):
        """Get Slack configuration from secrets"""
        return {
            "bot_token": self.get_secret("slack-bot-token"),
            "webhook_url": self.get_secret("slack-webhook-url"),
        }
    
    def get_salesforce_config(self):
        """Get Salesforce configuration from secrets"""
        config = {
            "client_id": self.get_secret("salesforce-client-id"),
            "client_secret": self.get_secret("salesforce-client-secret"),
            "username": self.get_secret("salesforce-username"),
            "password": self.get_secret("salesforce-password"),
            "security_token": self.get_secret("salesforce-security-token"),
        }
        
        # Get tokens if they exist
        tokens_json = self.get_secret("salesforce-tokens")
        if tokens_json:
            config["tokens"] = json.loads(tokens_json)
        
        return config
    
    def get_sql_server_config(self):
        """Get SQL Server configuration from secrets"""
        return {
            "host": self.get_secret("sql-server-host"),
            "database": self.get_secret("sql-server-database"),
            "username": self.get_secret("sql-server-username"),
            "password": self.get_secret("sql-server-password"),
        }

# Global instance
_secret_manager = None

def get_secret_manager(project_id=None):
    """Get or create the global SecretManager instance"""
    global _secret_manager
    if _secret_manager is None:
        _secret_manager = SecretManager(project_id)
    return _secret_manager