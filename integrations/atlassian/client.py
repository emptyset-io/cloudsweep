from atlassian import Confluence
import os

class AtlassianClient:
    """
    A client for interacting with Atlassian APIs (e.g., Confluence, Jira).
    Responsible for authentication and setting up the connection to Atlassian services.
    """
    def __init__(self, base_url=None, username=None, api_token=None):
        """
        Initialize the Atlassian client.

        :param base_url: Base URL for Atlassian service (e.g., Confluence or Jira).
        :param username: Email address for authentication (not username or userkey).
        :param api_token: API token for authentication.
        """
        # Use environment variables if parameters are not provided
        self.base_url = base_url or os.getenv("CS_ATLASSIAN_BASE_URL")
        self.username = username or os.getenv("CS_ATLASSIAN_USERNAME")  # Email address
        self.api_token = api_token or os.getenv("CS_ATLASSIAN_API_TOKEN")
        
        if not self.username or not self.api_token or not self.base_url:
            raise ValueError("Missing required Atlassian credentials or base URL.")
        
        # Initialize the Confluence client from the atlassian-python-api
        self.client = Confluence(
            url=self.base_url,
            username=self.username,
            password=self.api_token  # API token used as password
        )

    def authenticate(self):
        """
        Test the authentication by checking if the user exists or retrieving user info.

        :return: True if authentication is successful, else False.
        """
        try:
            # Attempt to fetch the current user's information from Confluence
            user_info = self.client.get_user_details_by_username(self.username)
            return user_info is not None
        except Exception as e:
            print(f"Authentication failed: {e}")
            return False

    def get_client(self):
        """
        Return the Confluence client object for use in other modules.
        
        :return: The Confluence client instance.
        """
        return self.client
