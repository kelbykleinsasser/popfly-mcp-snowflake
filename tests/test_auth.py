import pytest
import os
from unittest.mock import patch, MagicMock

from auth.snowflake_auth import get_snowflake_connection
from config.settings import settings

class TestSnowflakeAuth:
    
    @patch('auth.snowflake_auth.snowflake.connector.connect')
    @patch('builtins.open')
    @patch('auth.snowflake_auth.load_pem_private_key')
    def test_successful_connection(self, mock_load_key, mock_open, mock_connect):
        """Test successful Snowflake connection with RSA key"""
        # Mock private key
        mock_key = MagicMock()
        mock_key.private_bytes.return_value = b'mock_der_bytes'
        mock_load_key.return_value = mock_key
        
        # Mock file operations
        mock_file = MagicMock()
        mock_file.read.return_value = b'mock_pem_data'
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Mock connection
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        # Test connection
        result = get_snowflake_connection(
            account='test_account',
            user='test_user',
            private_key_path='test_path.pem',
            private_key_passphrase='test_pass'
        )
        
        # Assertions
        assert result == mock_conn
        mock_connect.assert_called_once()
        mock_load_key.assert_called_once()
    
    def test_missing_private_key_file(self):
        """Test error handling when private key file is missing"""
        with pytest.raises(FileNotFoundError):
            get_snowflake_connection(
                account='test_account',
                user='test_user',
                private_key_path='nonexistent_key.pem'
            )