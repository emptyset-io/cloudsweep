import datetime
from atlassian import Confluence
from utils.logger import get_logger
import pytz


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
        self.username = username
        # Initialize the AtlassianClient for authentication
        self.confluence = Confluence(
            url=confluence_url,
            username=username,
            password=api_token,
            cloud=True,
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
            response = self.confluence.get_space(space_key)
            if response:
                logger.info("Authentication successful.")
                return True
            else:
                logger.error("Authentication failed: No response received.")
                return False
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            logger.info("Stack trace: ", exc_info=True)
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
            logger.info("Stack trace: ", exc_info=True)
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
        content = """
            <h1>AWS Cost Report Overview</h1>

            <p>The AWS Cost Report provides a comprehensive view of resource usage and associated costs, enabling account owners to monitor and manage expenses effectively. This report aggregates data across <strong>hourly</strong>, <strong>daily</strong>, <strong>weekly</strong>, <strong>monthly</strong>, and <strong>lifetime</strong> periods, offering insights into cost trends over time. Each resource's cost is calculated to reflect its actual usage, helping to identify high-cost items and optimize resource allocation.</p>

            <p>By breaking costs down into granular time intervals, the report allows users to pinpoint spikes in spending, identify underutilized resources, and make data-driven decisions. The lifetime cost metric is particularly useful for understanding the total investment in long-standing resources.</p>

            <h2>Expectations for Account Owners</h2>

            <p>Account owners are expected to use this report to take proactive steps in resource management. The report highlights resources that may no longer be necessary, are underutilized, or are improperly scaled, which can drive up costs unnecessarily.</p>

            <p>Owners are encouraged to review their resource inventory and start cleaning up any unused or nonessential items. This includes terminating idle instances, deleting unused volumes and/or snapshots, downsizing over-provisioned services, and consolidating workloads where feasible. Regularly acting on these insights will help control costs, reduce waste, and ensure adherence to best practices for cloud resource management.</p>

            <p>By leveraging the AWS Cost Report, account owners can take ownership of their spending, improve operational efficiency, and contribute to a more streamlined and cost-effective cloud environment.</p>
            """
                    
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

    def _upload_attachment(self, page_id, report_file_path, title=None, content_type=None, comment=None, num_keep=7):
        """
        Uploads an attachment (file) to the specified Confluence page and cleans up old attachments,
        keeping only the latest `num_keep` attachments.

        :param page_id: The ID of the page to upload the attachment to
        :param report_file_path: Path to the report file
        :param title: (Optional) Title for the attachment
        :param content_type: (Optional) Content type for the attachment (e.g., "application/pdf")
        :param comment: (Optional) Comment to add with the attachment
        :param num_keep: The number of most recent attachments to retain
        """
        logger.info(f"Uploading attachment to page ID: {page_id} from file: {report_file_path}")
        
        try:
            # Step 1: Clean up old attachments on the page, retaining only the most recent `num_keep`
            logger.info("Cleaning up old attachments")
            report_file = report_file_path.split('/')[1]
            attachments = self.confluence.get_attachments_from_content(
                page_id=page_id,
                expand="version",
                filename=report_file
            ).get("results", [])
            
            if not attachments:
                logger.warning(f"No existing attachments found for file: {report_file} on page ID: {page_id}")
            else:
                self.confluence.remove_page_attachment_keep_version(page_id, report_file, num_keep)

            # Step 2: Upload the new attachment
            response = self.confluence.attach_file(
                filename=report_file_path,
                page_id=page_id,
                title=title,
                content_type=content_type,
                comment=comment
            )

            if 'results' in response and response['results']:
                attachment_info = response['results'][0]
                logger.debug(f"Attachment uploaded successfully: {attachment_info}")
            elif 'id' in response:
                logger.debug(f"Attachment uploaded successfully with ID: {response['id']}")
            else:
                logger.error("Unable to upload attachment: Invalid response format.")
                raise Exception(f"Error uploading attachment to page ID {page_id}: Invalid response format.")

        except Exception as e:
            logger.error(f"Error uploading attachment to page ID {page_id}: {str(e)}")
            logger.info("Stack trace: ", exc_info=True)
            raise
