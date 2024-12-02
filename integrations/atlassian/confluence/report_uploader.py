import requests
from integrations.atlassian.client import AtlassianClient
import os

class ConfluenceReportUploader:
    def __init__(self, confluence_url, username, api_token):
        # Initialize the AtlassianClient for Confluence
        self.atlassian_client = AtlassianClient(base_url=confluence_url, username=username, api_token=api_token)

    def upload_report(self, space_key, page_title, report_file_path, date, account_id):
        # First, authenticate using AtlassianClient
        if not self.atlassian_client.authenticate():
            raise Exception("Authentication with Confluence failed.")

        # Read the report file
        with open(report_file_path, "r") as file:
            report_content = file.read()

        # Create or find the page where the report will be uploaded
        page_id = self._get_or_create_page(space_key, page_title, date, account_id)

        # Upload the report as an attachment to the page
        self._upload_attachment(page_id, report_file_path)

    def _get_or_create_page(self, space_key, page_title, date, account_id):
        # Fetch the page if it exists, or create a new one if it doesn't
        existing_page = self.atlassian_client.get_page_by_title(space_key, page_title)
        if existing_page:
            return existing_page["id"]
        
        # If the page doesn't exist, create a new page
        content = f"Report for account {account_id} on {date}"
        new_page = self.atlassian_client.create_page(space_key, page_title, content)
        return new_page["id"]

    def _upload_attachment(self, page_id, report_file_path):
        # Upload the report file as an attachment to the Confluence page
        file_name = os.path.basename(report_file_path)
        self.atlassian_client.upload_attachment(page_id, report_file_path, file_name)
