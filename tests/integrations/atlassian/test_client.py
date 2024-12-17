import pytest
import responses
import os
from integrations.atlassian.client import AtlassianClient

# Default environment variable values for testing
DEFAULT_BASE_URL = "https://example.atlassian.net"
DEFAULT_USERNAME = "test_user"
DEFAULT_API_TOKEN = "test_token"

@pytest.fixture
def set_env_vars(monkeypatch):
    """Fixture to set up environment variables."""
    monkeypatch.setenv("CS_ATLASSIAN_BASE_URL", DEFAULT_BASE_URL)
    monkeypatch.setenv("CS_ATLASSIAN_USERNAME", DEFAULT_USERNAME)
    monkeypatch.setenv("CS_ATLASSIAN_API_TOKEN", DEFAULT_API_TOKEN)

@pytest.fixture
def client(set_env_vars):
    """Fixture for initializing the AtlassianClient using environment variables."""
    base_url = os.getenv("CS_ATLASSIAN_BASE_URL")
    username = os.getenv("CS_ATLASSIAN_USERNAME")
    api_token = os.getenv("CS_ATLASSIAN_API_TOKEN")
    return AtlassianClient(base_url=base_url, username=username, api_token=api_token)

@responses.activate
def test_authenticate_success(client):
    """Test successful authentication."""
    endpoint = "/rest/api/user"
    responses.add(
        responses.GET,
        f"{DEFAULT_BASE_URL}{endpoint}",
        json={"username": DEFAULT_USERNAME},
        status=200
    )

    assert client.authenticate() is True

@responses.activate
def test_authenticate_failure(client):
    """Test failed authentication."""
    endpoint = "/rest/api/user"
    responses.add(
        responses.GET,
        f"{DEFAULT_BASE_URL}{endpoint}",
        status=401
    )

    assert client.authenticate() is False

@responses.activate
def test_request_success(client):
    """Test a successful request."""
    endpoint = "/rest/api/example"
    responses.add(
        responses.GET,
        f"{DEFAULT_BASE_URL}{endpoint}",
        json={"key": "value"},
        status=200
    )

    response = client.request("GET", endpoint)
    assert response == {"key": "value"}

@responses.activate
def test_request_failure(client):
    """Test a failed request."""
    endpoint = "/rest/api/example"
    responses.add(
        responses.GET,
        f"{DEFAULT_BASE_URL}{endpoint}",
        status=404
    )

    with pytest.raises(Exception):
        client.request("GET", endpoint)

@responses.activate
def test_request_with_params(client):
    """Test a request with query parameters."""
    endpoint = "/rest/api/example"
    params = {"key": "value"}
    responses.add(
        responses.GET,
        f"{DEFAULT_BASE_URL}{endpoint}",
        match=[responses.matchers.query_param_matcher(params)],
        json={"result": "success"},
        status=200
    )

    response = client.request("GET", endpoint, params=params)
    assert response == {"result": "success"}

@responses.activate
def test_request_with_body(client):
    """Test a POST request with a body."""
    endpoint = "/rest/api/example"
    payload = {"key": "value"}
    responses.add(
        responses.POST,
        f"{DEFAULT_BASE_URL}{endpoint}",
        match=[responses.matchers.json_params_matcher(payload)],
        json={"result": "created"},
        status=201
    )

    response = client.request("POST", endpoint, json=payload)
    assert response == {"result": "created"}

def test_missing_env_vars(monkeypatch):
    """Test initialization with missing environment variables."""
    monkeypatch.delenv("CS_ATLASSIAN_BASE_URL", raising=False)
    monkeypatch.delenv("CS_ATLASSIAN_USERNAME", raising=False)
    monkeypatch.delenv("CS_ATLASSIAN_API_TOKEN", raising=False)

    with pytest.raises(ValueError, match="Missing required Atlassian credentials or base URL."):
        AtlassianClient(
            base_url=os.getenv("CS_ATLASSIAN_BASE_URL"),
            username=os.getenv("CS_ATLASSIAN_USERNAME"),
            api_token=os.getenv("CS_ATLASSIAN_API_TOKEN")
        )
