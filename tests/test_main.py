import pytest
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime, timezone
import os
from main import (
    setup_scanners,
    parse_and_prepare_args,
    is_scan_results_empty,
    generate_report,
    extract_account_details_from_scan_results,
    upload_report_to_confluence,
    handle_confluence_upload,
    main,
)

@pytest.fixture
def mock_args():
    args = MagicMock()
    args.organization_role = "org-role"
    args.runner_role = "runner-role"
    args.max_workers = 8  # Updated to match expected default
    args.upload_confluence = False
    return args
@pytest.fixture
def mock_session_manager():
    return MagicMock()

@pytest.fixture
def mock_scanners():
    return [MagicMock(), MagicMock()]
@pytest.fixture
def mock_scanner():
    scanner = MagicMock()
    scanner.name = "test_scanner"
    scanner.__str__ = lambda x: "test_scanner"
    return scanner
@pytest.fixture
def mock_regions():
    return ["us-east-1", "us-west-2"]

@pytest.fixture
def mock_accounts():
    # Return actual strings instead of MagicMock objects
    return ["123456789012", "210987654321"]


@pytest.fixture
def sample_scan_results():
    return [
        {
            "account_id": "123456789012",
            "account_name": "test-account",
            "scan_results": {
                "us-east-1": {
                    "ec2": [{"ResourceId": "i-1234"}]
                }
            }
        }
    ]
@pytest.fixture
def mock_session_manager():
    session_manager = MagicMock()
    session_manager.get_regions.return_value = ["us-east-1", "us-west-2"]
    session_manager.credentials = MagicMock()
    session_manager.credentials.access_key = "test-key"
    return session_manager
@pytest.fixture
def sample_scan_metrics():
    return {
        "start_time": datetime.now(timezone.utc),  # Use timezone-aware datetime
        "duration": 60,
        "total_resources": 10
    }
def test_setup_scanners():
    with patch('main.ResourceScannerRegistry.register_scanners_from_directory') as mock_register:
        setup_scanners()
        mock_register.assert_called_once_with("scanner/aws/services")

@patch('main.AWSSessionManager')  # Add this patch
@patch('main.ArgumentParser')
def test_parse_and_prepare_args(mock_arg_parser, mock_args, mock_session_manager, mock_scanner):
    # Setup mock returns
    mock_arg_parser.parse_arguments.return_value = mock_args
    mock_arg_parser.get_scanners.return_value = [mock_scanner]
    mock_arg_parser.get_regions.return_value = ["us-east-1", "us-west-2"]
    mock_arg_parser.get_accounts.return_value = ["123456789012", "210987654321"]
       # Mock the session manager constructor
    mock_session_manager.return_value = MagicMock(
        regions=["us-east-1", "us-west-2"],
        credentials=MagicMock(access_key="test-key")
    )
    args, scanners, regions, session_manager, accounts = parse_and_prepare_args()
    
    assert args == mock_args
    assert isinstance(scanners[0], MagicMock)  # Changed to expect MagicMock
    assert isinstance(regions[0], str)
    assert isinstance(accounts[0], str)
    assert len(scanners) > 0
    assert len(regions) > 0
    assert len(accounts) > 0
def test_is_scan_results_empty_with_results(sample_scan_results):
    assert not is_scan_results_empty(sample_scan_results)

def test_is_scan_results_empty_without_results():
    empty_results = [{"scan_results": {"us-east-1": {"ec2": []}}}]
    assert is_scan_results_empty(empty_results)

@patch('main.generate_html_report')
def test_generate_report(mock_generate_html, sample_scan_results, sample_scan_metrics):
    mock_generate_html.return_value = "report.html"
    result = generate_report(sample_scan_results, sample_scan_metrics)
    assert result == "report.html"

def test_extract_account_details_from_scan_results(sample_scan_results):
    result = extract_account_details_from_scan_results(sample_scan_results)
    assert result == {"123456789012": "test-account"}

@patch('main.ConfluenceReportUploader')
@patch.dict(os.environ, {
    "CS_ATLASSIAN_BASE_URL": "https://confluence.example.com",
    "CS_ATLASSIAN_USERNAME": "user",
    "CS_ATLASSIAN_API_TOKEN": "token",
    "CS_CONFLUENCE_PARENT_PAGE": "123",
    "CS_CONFLUENCE_SPACE_KEY": "SPACE"
})
def test_upload_report_to_confluence(mock_confluence_uploader):
    account_details = {"123456789012": "test-account"}
    upload_report_to_confluence("report.html", account_details)
    mock_confluence_uploader.return_value.upload_report.assert_called_once()

def test_handle_confluence_upload(mock_args):
    with patch('main.upload_report_to_confluence') as mock_upload:
        mock_args.upload_confluence = True
        handle_confluence_upload(mock_args, "report.html", {"123": "test"})
        mock_upload.assert_called_once_with("report.html", {"123": "test"})

@patch('main.setup_scanners')
@patch('main.parse_and_prepare_args')
@patch('main.Executor')
@patch('main.generate_report')
@patch('main.extract_account_details_from_scan_results')
@patch('main.handle_confluence_upload')
def test_main(
    mock_handle_confluence,
    mock_extract_details,
    mock_generate_report,
    mock_executor,
    mock_parse_args,
    mock_setup,
    mock_args,
    mock_session_manager,
    mock_scanners,
    mock_regions,
    mock_accounts,
    sample_scan_results,
    sample_scan_metrics
):
    mock_parse_args.return_value = (mock_args, ["scanner1"], ["us-east-1"], mock_session_manager, ["123456789012"])
    mock_executor.return_value.execute.return_value = (sample_scan_results, sample_scan_metrics)
    mock_generate_report.return_value = "report.html"
    mock_extract_details.return_value = {"123": "test"}

    main()

    mock_setup.assert_called_once()
    mock_parse_args.assert_called_once()
    mock_executor.assert_called_once()
    mock_generate_report.assert_called_once()
    mock_handle_confluence.assert_called_once()

def test_main_handles_exception():
    with patch('main.setup_scanners', side_effect=Exception("Test error")):
        with patch('main.logger.exception') as mock_logger:
            main()
            mock_logger.assert_called_once()