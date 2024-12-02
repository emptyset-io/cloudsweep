import requests

class AtlassianClient:
    """
    Generic Atlassian client for handling authentication and requests.
    """
    def __init__(self, base_url, username, api_token):
        """
        Initialize the Atlassian client.
        
        :param base_url: Base URL for Atlassian service (e.g., Confluence or Jira).
        :param username: Username for authentication.
        :param api_token: API token for authentication.
        """
        self.base_url = base_url.rstrip('/')
        self.auth = (username, api_token)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def request(self, method, endpoint, **kwargs):
        """
        Perform a request to the Atlassian API.
        
        :param method: HTTP method (GET, POST, PUT, DELETE).
        :param endpoint: API endpoint (relative to base URL).
        :param kwargs: Additional arguments for the request (e.g., `json`, `params`).
        :return: Response object.
        """
        url = f"{self.base_url}{endpoint}"
        response = requests.request(method, url, auth=self.auth, headers=self.headers, **kwargs)
        response.raise_for_status()  # Raise an error for HTTP 4xx/5xx responses
        return response.json()
