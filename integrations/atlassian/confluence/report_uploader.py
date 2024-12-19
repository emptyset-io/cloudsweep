import datetime
from atlassian import Confluence
from integrations.atlassian.client import AtlassianClient
from utils.logger import get_logger


# Set up the logger
logger = get_logger(__name__)

class ConfluenceReportUploader:
    def __init__(self, confluence_url, username, api_token, parent_page_title="Cost Reports"):
        """
        Initializes the ConfluenceReportUploader with the provided Confluence URL, 
        username, API token, and parent page title.
        
        :param confluence_url: URL of the Confluence instance
        :param username: Username for authentication
        :param api_token: API token for authentication
        :param parent_page_title: Title of the parent page (default is "Cost Reports")
        """
        # Initialize the AtlassianClient for authentication
        self.atlassian_client = AtlassianClient(base_url=confluence_url, username=username, api_token=api_token)
        self.confluence = Confluence(
            url=confluence_url,
            username=username,
            password=api_token
        )
        self.date = datetime.datetime.now().strftime("%m/%d/%Y")
        self.parent_page_title = parent_page_title

    def upload_report(self, space_key, page_title, report_file_path, account_id, title=None, content_type=None, comment=None):
        """
        Uploads a report to Confluence by checking authentication, fetching or creating a page, 
        and uploading an attachment to the page.
        
        :param space_key: The Confluence space key
        :param page_title: Title of the page where the report will be uploaded
        :param report_file_path: Path to the report file
        :param account_id: Account ID associated with the report
        :param title: (Optional) Title for the attachment
        :param content_type: (Optional) Content type for the attachment (e.g., "application/pdf")
        :param comment: (Optional) Comment to add with the attachment
        """
        # Authenticate and check if authentication is successful
        if not self._authenticate_confluence(space_key):
            raise Exception("Authentication with Confluence failed.")
        
        # Get parent page ID based on title ("Cost Reports")
        parent_page_id = self._get_parent_page_id(space_key)

        # Create or fetch the page where the report will be uploaded
        page_id = self._get_or_create_page(space_key, page_title, account_id, parent_page_id)
        
        # Upload the report as an attachment to the page
        self._upload_attachment(page_id, report_file_path, title, content_type, comment)

    def _authenticate_confluence(self, space_key):
        """
        Authenticates the client by performing a simple API request to verify credentials.
        
        :param space_key: The Confluence space key (not used here but can be useful for space-specific operations)
        :return: True if authentication succeeds, False otherwise
        """
        try:
            logger.info(f"Authenticating with Confluence for space: {space_key}")
            # Perform a simple API request to verify authentication
            response = self.atlassian_client.authenticate()
            if response:
                logger.info("Authentication successful.")
                return True
            else:
                logger.error("Authentication failed: No response received.")
                return False
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            logger.debug("Stack trace: ", exc_info=True)
            return False

    def _get_parent_page_id(self, space_key):
        """
        Fetches the page ID of the parent page (Cost Reports folder).
        
        :param space_key: The Confluence space key
        :return: Parent page ID
        :raises: Exception if the parent page cannot be found
        """
        try:
            # Check if the parent page title is an integer (i.e., it's likely an ID)
            if isinstance(self.parent_page_title, int):
                return self.parent_page_title  # Return the ID directly
            
            logger.info(f"Fetching parent page ID for space: {space_key}, title: {self.parent_page_title}")
            pages = self.confluence.get_all_pages_from_space(space_key, start=0, limit=100, expand='version')

            for page in pages:
                if page['title'] == self.parent_page_title:
                    logger.info(f"Found parent page: {self.parent_page_title}, ID: {page['id']}")
                    return page['id']
            
            logger.error(f"Parent page '{self.parent_page_title}' not found in space {space_key}.")
            raise Exception(f"Parent page '{self.parent_page_title}' not found in space {space_key}.")
        except Exception as e:
            logger.error(f"Error fetching parent page ID: {str(e)}")
            logger.debug("Stack trace: ", exc_info=True)
            raise

    def _get_or_create_page(self, space_key, page_title, account_id, parent_page_id):
        """
        Fetches an existing page by title or creates a new one if not found.
        
        :param space_key: The Confluence space key
        :param page_title: Title of the page to fetch or create
        :param account_id: Account ID to include in the page content
        :param parent_page_id: Parent page ID where the new page will be created
        :return: The page ID of the existing or newly created page
        """
        logger.info(f"Checking if page '{page_title}' exists in space '{space_key}'...")
        existing_page = self._get_page_by_title(space_key, page_title)
        if existing_page:
            logger.info(f"Page '{page_title}' already exists. Returning existing page ID.")
            return existing_page["id"]

        logger.info(f"Page '{page_title}' does not exist. Creating new page...")
        return self._create_page(space_key, page_title, account_id, parent_page_id)["id"]

    def _get_page_by_title(self, space_key, page_title):
        """
        Searches for a page by title in the given space.
        
        :param space_key: The Confluence space key
        :param page_title: The title of the page to search for
        :return: The page if found, None otherwise
        """
        logger.info(f"Searching for page with title '{page_title}' in space '{space_key}'...")
        pages = self.confluence.get_all_pages_from_space(space_key, start=0, limit=100, expand='version')

        # Find the page by title
        for page in pages:
            if page['title'] == page_title:
                logger.info(f"Found page with title '{page_title}', ID: {page['id']}")
                return page
        
        logger.info(f"Page with title '{page_title}' not found.")
        return None

    def _create_page(self, space_key, page_title, account_id, parent_page_id):
        """
        Creates a new page with the specified title and content in the specified space.
        
        :param space_key: The Confluence space key
        :param page_title: Title of the new page
        :param account_id: Account ID to include in the page content
        :param parent_page_id: Parent page ID where the new page will be created
        :return: The response from the Confluence API containing the new page's data
        """
        logger.info(f"Creating new page '{page_title}' under parent page ID {parent_page_id}...")
        content = f"Report for account {account_id} on {self.date}"
        
        # Add the attachments macro to the page content
        attachment_macro = f"<ac:macro ac:name=\"attachments\" ac:schema-version=\"1\"></ac:macro>"
        page_body = f"{content}<br><br>{attachment_macro}"
        
        page_data = {
            "type": "page",
            "title": page_title,
            "space": {"key": space_key},
            "body": {
                "storage": {
                    "value": page_body,
                    "representation": "storage"
                }
            },
            "ancestors": [{"id": parent_page_id}]  # Set the parent page ID here
        }
        
        # Create the page using the Confluence API
        new_page = self.confluence.create_page(space_key, page_title, page_body, parent_id=parent_page_id)
        logger.info(f"Page '{page_title}' created successfully with ID: {new_page['id']}")
        
        return new_page

    def _upload_attachment(self, page_id, report_file_path, title=None, content_type=None, comment=None):
        """
        Uploads an attachment (file) to the specified Confluence page.
        
        :param page_id: The ID of the page to upload the attachment to
        :param report_file_path: Path to the report file
        :param title: (Optional) Title for the attachment
        :param content_type: (Optional) Content type for the attachment (e.g., "application/pdf")
        :param comment: (Optional) Comment to add with the attachment
        """
        logger.info(f"Uploading attachment to page ID: {page_id} from file: {report_file_path}")
        
        try:
            # Ensure the report_file_path is a string and not a file object
            if isinstance(report_file_path, str):
                # Use attach_file with optional parameters like title, content_type, and comment
                response = self.confluence.attach_file(
                    filename=report_file_path,  # Path to the file
                    page_id=page_id,  # The ID of the page to attach to
                    title=title,  # Optional: provide title for the attachment
                    content_type=content_type,  # Optional: provide content type (e.g., "application/pdf")
                    comment=comment  # Optional: provide a comment for the attachment
                )
            else:
                raise ValueError("The report file path must be a string representing the file path.")

            # Check if the response is in the first-time upload format (with 'results')
            if 'results' in response and response['results']:
                attachment_info = response['results'][0]  # Get the first result
                attachment_id = attachment_info.get('id')
                attachment_title = attachment_info.get('title')
            # Check if the response is in the replace format (with just 'id')
            elif 'id' in response:
                attachment_id = response.get('id')
                attachment_title = response.get('title')
            else:
                logger.error("Unable to upload attachment: response format is invalid.")
                raise Exception(f"Error uploading attachment to page ID {page_id}: Invalid response format.")

            # Log successful upload
            logger.info(f"Attachment uploaded successfully to page ID: {page_id} with attachment ID: {attachment_id}")

        except Exception as e:
            logger.error(f"Error uploading attachment to page ID {page_id}: {str(e)}")
            logger.debug("Stack trace: ", exc_info=True)
            raise Exception(f"Error uploading attachment to page ID {page_id}: {str(e)}")  # Ensure the message includes the page ID
