import requests
import os

class AtlassianClient:
    """
    Generic Atlassian client for handling authentication and requests.
    """
    def __init__(self, base_url=None, username=None, api_token=None):
        """
        Initialize the Atlassian client.
        
        :param base_url: Base URL for Atlassian service (e.g., Confluence or Jira).
        :param username: Username for authentication.
        :param api_token: API token for authentication.
        """
        # Use environment variables if parameters are not provided
        self.base_url = base_url or os.getenv("CS_ATLASSIAN_BASE_URL")
        self.auth = (username or os.getenv("CS_ATLASSIAN_USERNAME"), 
                     api_token or os.getenv("CS_ATLASSIAN_API_TOKEN"))
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if not all(self.auth) or not self.base_url:
            raise ValueError("Missing required Atlassian credentials or base URL.")


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
    
    def authenticate(self):
        """
        Test the authentication by fetching user details.
        
        :return: True if authentication is successful.
        """
        try:
            response = self.request("GET", "/rest/api/user", params={"username": self.auth[0]})
            return response is not None
        except requests.HTTPError as e:
            print(f"Authentication failed: {e}")
            return False
        
