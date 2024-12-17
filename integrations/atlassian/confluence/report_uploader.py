import requests
import datetime
from integrations.atlassian.client import AtlassianClient
import os

class ConfluenceReportUploader:
    def __init__(self, confluence_url, username, api_token, parent_page_title=None):
        # Initialize the AtlassianClient for Confluence
        self.atlassian_client = AtlassianClient(base_url=confluence_url, username=username, api_token=api_token)
        self.date = datetime.datetime.now().strftime("%m/%d/%Y")
        self.parent_page_title = parent_page_title

    def upload_report(self, space_key, page_title, report_file_path, account_id):
        # First, authenticate using AtlassianClient
        if not self.atlassian_client.authenticate():
            raise Exception("Authentication with Confluence failed.")

        # Create or find the page where the report will be uploaded
        page_id = self._get_or_create_page(space_key, page_title, account_id)

        # Upload the report as an attachment to the page
        self._upload_attachment(page_id, report_file_path)

    def _get_or_create_page(self, space_key, page_title, account_id):
        # Fetch the page if it exists, or create a new one if it doesn't
        existing_page = self._get_page_by_title(space_key, page_title)
        if existing_page:
            return existing_page["id"]
        
        # If the page doesn't exist, create a new page
        content = f"Report for account {account_id} on {self.date}"
        new_page = self._create_page(space_key, page_title, content)
        return new_page["id"]

    def _get_page_by_title(self, space_key, page_title):
        # Construct the API endpoint to search for the page by title
        url = f"{self.atlassian_client.base_url}/rest/api/content"
        params = {
            'spaceKey': space_key,
            'title': page_title,
            'expand': 'version'
        }
        
        if self.parent_page_title:
            params['ancestors'] = self.parent_page_title
        
        response = requests.get(url, auth=(self.atlassian_client.username, self.atlassian_client.api_token), params=params)

        if response.status_code == 200:
            pages = response.json().get('results', [])
            if pages:
                # Return the first page that matches the title (in case of multiple results)
                return pages[0]
        
        return None

    def _create_page(self, space_key, page_title, content):
        # Create a new page in Confluence under the provided space_key with the given content
        url = f"{self.atlassian_client.base_url}/rest/api/content"
        page_data = {
            "type": "page",
            "title": page_title,
            "space": {"key": space_key},
            "body": {
                "storage": {
                    "value": content,
                    "representation": "storage"
                }
            }
        }

        if self.parent_page_title:
            parent_page = self._get_page_by_title(space_key, self.parent_page_title)
            if parent_page:
                page_data["ancestors"] = [{"id": parent_page["id"]}]
        
        response = requests.post(url, auth=(self.atlassian_client.username, self.atlassian_client.api_token), json=page_data)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to create page: {response.status_code} - {response.text}")

    def _upload_attachment(self, page_id, report_file_path):
        # Upload the report file as an attachment to the Confluence page
        file_name = os.path.basename(report_file_path)
        self.atlassian_client.upload_attachment(page_id, report_file_path, file_name)
