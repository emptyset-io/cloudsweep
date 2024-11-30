import pytest
from unittest.mock import MagicMock, patch
from integrations.atlassian.confluence.report_uploader import ConfluenceReportUploader

# Test successful report upload
@patch('integrations.atlassian.confluence.report_uploader.Confluence')
def test_upload_report_success(mock_confluence):
    # Set up the mock for Confluence API calls
    mock_confluence_instance = MagicMock()
    mock_confluence.return_value = mock_confluence_instance
    mock_confluence_instance.get_all_pages_from_space.return_value = [{"title": "Cost Reports", "id": "123"}]
    mock_confluence_instance.get_page_by_title.return_value = None  # Simulate that page doesn't exist
    mock_confluence_instance.create_page.return_value = {"id": "456"}  # Simulate page creation
    mock_confluence_instance.attach_file.return_value = {"results": [{"id": "789", "title": "Report.pdf"}]}  # Simulate file upload success
    
    # Initialize the uploader
    uploader = ConfluenceReportUploader(
        confluence_url="https://example.atlassian.net",
        username="user@example.com",
        api_token="mock_api_token"
    )
    
    # Call upload_report and assert no exceptions are raised
    uploader.upload_report(
        space_key="SPACE",
        page_title="Test Report",
        report_file_path="path/to/report.pdf",
        account_id="12345"
    )
    
    # Ensure methods are called with expected arguments
    mock_confluence_instance.get_all_pages_from_space.assert_any_call("SPACE", start=0, limit=100, expand='version')


# Test failed authentication
@patch('integrations.atlassian.confluence.report_uploader.Confluence')
def test_upload_report_authentication_failure(mock_confluence):
    # Set up the mock for Confluence API calls
    mock_confluence_instance = MagicMock()
    mock_confluence.return_value = mock_confluence_instance
    mock_confluence_instance.get_space.side_effect = Exception("Authentication failed")  # Simulate authentication failure

    # Initialize the uploader
    uploader = ConfluenceReportUploader(
        confluence_url="https://example.atlassian.net",
        username="user@example.com",
        api_token="mock_api_token"
    )

    # Assert that an exception is raised during upload due to failed authentication
    with pytest.raises(Exception, match="Authentication with Confluence failed."):
        uploader.upload_report(
            space_key="SPACE",
            page_title="Test Report",
            report_file_path="path/to/report.pdf",
            account_id="12345"
        )

# Test parent page ID fetching (with page found)
@patch('integrations.atlassian.confluence.report_uploader.Confluence')
def test_get_parent_page_id_found(mock_confluence):
    # Set up the mock for Confluence API calls
    mock_confluence_instance = MagicMock()
    mock_confluence.return_value = mock_confluence_instance
    mock_confluence_instance.get_all_pages_from_space.return_value = [
        {"title": "Cost Reports", "id": "123"}
    ]

    # Initialize the uploader
    uploader = ConfluenceReportUploader(
        confluence_url="https://example.atlassian.net",
        username="user@example.com",
        api_token="mock_api_token"
    )

    # Test the parent page ID retrieval
    parent_page_id = uploader._get_parent_page_id("SPACE")
    assert parent_page_id == "123"  # Assert the correct ID is returned

# Test parent page ID fetching (page not found)
@patch('integrations.atlassian.confluence.report_uploader.Confluence')
def test_get_parent_page_id_not_found(mock_confluence):
    # Set up the mock for Confluence API calls
    mock_confluence_instance = MagicMock()
    mock_confluence.return_value = mock_confluence_instance
    mock_confluence_instance.get_all_pages_from_space.return_value = []

    # Initialize the uploader
    uploader = ConfluenceReportUploader(
        confluence_url="https://example.atlassian.net",
        username="user@example.com",
        api_token="mock_api_token"
    )

    # Test the parent page ID retrieval with an exception
    with pytest.raises(Exception, match="Parent page 'Cost Reports' not found in space SPACE."):
        uploader._get_parent_page_id("SPACE")

# Test page creation logic
@patch('integrations.atlassian.confluence.report_uploader.Confluence')
def test_create_page(mock_confluence):
    # Set up the mock for Confluence API calls
    mock_confluence_instance = MagicMock()
    mock_confluence.return_value = mock_confluence_instance
    mock_confluence_instance.create_page.return_value = {"id": "456"}

    # Initialize the uploader
    uploader = ConfluenceReportUploader(
        confluence_url="https://example.atlassian.net",
        username="user@example.com",
        api_token="mock_api_token"
    )

    # Test the page creation
    page_data = uploader._create_page("SPACE", "Test Page", "12345", "123")
    assert page_data["id"] == "456"  # Assert the page ID returned from creation

# Test attachment upload
@patch('integrations.atlassian.confluence.report_uploader.Confluence')
def test_upload_attachment(mock_confluence):
    # Set up the mock for Confluence API calls
    mock_confluence_instance = MagicMock()
    mock_confluence.return_value = mock_confluence_instance
    mock_confluence_instance.attach_file.return_value = {"results": [{"id": "789", "title": "Report.pdf"}]}

    # Initialize the uploader
    uploader = ConfluenceReportUploader(
        confluence_url="https://example.atlassian.net",
        username="user@example.com",
        api_token="mock_api_token"
    )

    # Test uploading the attachment
    uploader._upload_attachment("456", "path/to/report.pdf")
    mock_confluence_instance.attach_file.assert_called_once_with(
        filename="path/to/report.pdf",
        page_id="456",
        title=None,
        content_type=None,
        comment=None
    )

# Test failed attachment upload
@patch('integrations.atlassian.confluence.report_uploader.Confluence')
def test_upload_attachment_failure(mock_confluence):
    # Set up the mock for Confluence API calls
    mock_confluence_instance = MagicMock()
    mock_confluence.return_value = mock_confluence_instance
    mock_confluence_instance.attach_file.side_effect = Exception("Upload failed")

    # Initialize the uploader
    uploader = ConfluenceReportUploader(
        confluence_url="https://example.atlassian.net",
        username="user@example.com",
        api_token="mock_api_token"
    )

    # Test failed upload with the updated exception message
    with pytest.raises(Exception, match="Error uploading attachment to page ID 456: Upload failed"):
        uploader._upload_attachment("456", "path/to/report.pdf")
