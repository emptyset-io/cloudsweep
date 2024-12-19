import pytest
from unittest.mock import MagicMock, patch
from integrations.atlassian.client import AtlassianClient  # Replace with your actual module
import os


# Test: Initialization with missing credentials
def test_atlassian_client_init_missing_credentials():
    with patch.dict(os.environ, {}, clear=True):  # Clear environment variables
        with pytest.raises(ValueError, match="Missing required Atlassian credentials or base URL."):
            AtlassianClient()  # Should raise ValueError since no credentials are provided


# Test: Initialization with provided credentials
def test_atlassian_client_init_with_credentials():
    with patch.dict(os.environ, {
        "CS_ATLASSIAN_BASE_URL": "https://example.atlassian.net",
        "CS_ATLASSIAN_USERNAME": "user@example.com",
        "CS_ATLASSIAN_API_TOKEN": "mock_api_token"
    }):
        client = AtlassianClient()
        assert client.base_url == "https://example.atlassian.net"
        assert client.username == "user@example.com"
        assert client.api_token == "mock_api_token"
        assert client.client is not None  # The Confluence client should be initialized


# Test: Initialization with environment variables when no parameters are passed
def test_atlassian_client_init_with_env_vars():
    with patch.dict(os.environ, {
        "CS_ATLASSIAN_BASE_URL": "https://example.atlassian.net",
        "CS_ATLASSIAN_USERNAME": "user@example.com",
        "CS_ATLASSIAN_API_TOKEN": "mock_api_token"
    }):
        client = AtlassianClient(base_url=None, username=None, api_token=None)
        assert client.base_url == "https://example.atlassian.net"
        assert client.username == "user@example.com"
        assert client.api_token == "mock_api_token"

# Test: Authentication - Failed authentication due to missing user
def test_authenticate_failure():
    mock_confluence_client = MagicMock()
    mock_confluence_client.get_user.side_effect = Exception("User not found")

    with patch("atlassian.Confluence", return_value=mock_confluence_client):
        client = AtlassianClient(
            base_url="https://example.atlassian.net",
            username="user@example.com",
            api_token="mock_api_token"
        )

        assert client.authenticate() is False  # Should return False as authentication failed

# Test: Authentication - Successful authentication
def test_authenticate_success():
    mock_confluence_client = MagicMock()

    # Correct method to mock is `get_user_details_by_username`
    mock_confluence_client.get_user_details_by_username.return_value = {"username": "user@example.com"}

    # Patch where the `Confluence` class is used in the `AtlassianClient` class
    with patch("integrations.atlassian.client.Confluence", return_value=mock_confluence_client):
        client = AtlassianClient(
            base_url="https://example.atlassian.net",
            username="user@example.com",
            api_token="mock_api_token"
        )

        # Now authenticate should return True as we're mocking the authentication success
        assert client.authenticate() is True  # Should return True as authentication is successful
# Test: get_client - Return the Confluence client instance
def test_get_client():
    mock_confluence_client = MagicMock()
    
    with patch("integrations.atlassian.client.Confluence", return_value=mock_confluence_client):
        client = AtlassianClient(
            base_url="https://example.atlassian.net",
            username="user@example.com",
            api_token="mock_api_token"
        )
    
        result = client.get_client()
    
        # Ensure that the get_client method returns the mock client, not the real instance
        assert result is mock_confluence_client  # Should return the mocked Confluence client
# Test: Initialization with missing environment variables
def test_atlassian_client_init_with_missing_env_vars():
    with patch.dict(os.environ, {}, clear=True):  # Ensure the env vars are missing
        with pytest.raises(ValueError, match="Missing required Atlassian credentials or base URL."):
            AtlassianClient()  # Should raise ValueError when credentials are not available


