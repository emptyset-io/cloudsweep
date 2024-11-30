import pytest
import os
import time
from unittest.mock import MagicMock, patch, call
from scanner.executor import Executor
from scanner.aws.account_scanner import AWSAccountScanner

@pytest.fixture
def mock_session_manager():
    """Fixture to mock the AWSSessionManager."""
    session_manager = MagicMock()
    session_manager.assume_destination_role_in_all_accounts.return_value = [MagicMock()]
    return session_manager

@pytest.fixture
def mock_aws_account_scanner():
    """Fixture to mock AWSAccountScanner."""
    with patch("scanner.executor.AWSAccountScanner") as MockScanner:
        yield MockScanner

@pytest.fixture
def executor(mock_session_manager):
    """Fixture to create an instance of the Executor class."""
    return Executor(session=mock_session_manager, scanners=["Scanner1", "Scanner2"], regions=["us-east-1"], max_workers=5)

def test_executor_initialization(mock_session_manager):
    """Test initialization of the Executor class."""
    executor = Executor(session=mock_session_manager, scanners=["Scanner1"], regions=["us-east-1"], max_workers=5)
    assert executor.session == mock_session_manager
    assert executor.scanners == ["Scanner1"]
    assert executor.regions == ["us-east-1"]
    assert executor.max_workers == 5
    assert executor.total_scans == 0
    assert executor.start_time is None
    assert executor.end_time is None
    assert executor.scan_metrics == {}

@patch("os.cpu_count", return_value=11)  # Mocking os.cpu_count to return 11 (or any desired number)
def test_executor_default_max_workers(mock_session_manager):
    """Test default max_workers if not explicitly set."""
    executor = Executor(session=mock_session_manager)
    # Assert max_workers is os.cpu_count() - 1 (in this case, 11 - 1 = 10)
    assert executor.max_workers == (11 - 1)  # Expected max_workers will be 10

def test_get_regions_for_session(executor, mock_session_manager):
    """Test the _get_regions_for_session method."""
    mock_session = MagicMock()
    mock_session.get_regions.return_value = ["us-east-1", "us-west-2"]

    # Case 1: Explicit regions
    executor.regions = ["us-east-1"]
    assert executor._get_regions_for_session(mock_session) == ["us-east-1"]

    # Case 2: All regions
    executor.regions = "all"
    assert executor._get_regions_for_session(mock_session) == ["us-east-1", "us-west-2"]

    # Case 3: No regions specified
    executor.regions = []
    assert executor._get_regions_for_session(mock_session) == ["us-east-1", "us-west-2"]

def test_scan_region_scanner(executor, mock_aws_account_scanner, mock_session_manager):
    """Test the _scan_region_scanner method."""
    mock_scanner = MagicMock()
    mock_session = MagicMock()
    account_id = "123456789012"
    region = "us-east-1"
    scanner_name = "Scanner1"

    # Successful scan
    mock_scanner.scan_resources.return_value = {"result": "success"}
    result = executor._scan_region_scanner(mock_scanner, mock_session, account_id, region, scanner_name)
    assert result == {"result": "success"}
    mock_scanner.scan_resources.assert_called_once_with(mock_session, account_id, [region], [scanner_name])

    # Scan failure
    mock_scanner.scan_resources.side_effect = Exception("Scan error")
    result = executor._scan_region_scanner(mock_scanner, mock_session, account_id, region, scanner_name)
    assert result is None

# @patch("scanner.executor.ThreadPoolExecutor")
# def test_execute(mock_thread_pool_executor, executor, mock_aws_account_scanner, mock_session_manager):
#     """Test the execute method."""
#     # Arrange
#     mock_session_manager.assume_destination_role_in_all_accounts.return_value = [
#         MagicMock(get_account_id=MagicMock(return_value="123456789012"), get_regions=MagicMock(return_value=["us-east-1"]))
#     ]
    
#     # Create a mock future and set it up so that result() returns the expected value
#     mock_future = MagicMock()
#     mock_future.result.side_effect = [{"result": "success"}, Exception("Scan error")]
    
#     # Mock the behavior of ThreadPoolExecutor's context manager
#     mock_thread_pool_executor.return_value.__enter__.return_value.submit.return_value = mock_future
#     mock_thread_pool_executor.return_value.__enter__.return_value.as_completed.return_value = iter([mock_future])
    
#     # Act
#     results = executor.execute()

#     # Assert
#     assert len(results) == 1
#     assert results[0] == {"result": "success"}
#     assert executor.total_scans == 1
#     assert "total_run_time" in executor.scan_metrics
#     assert "avg_scans_per_second" in executor.scan_metrics

#     # Verify ThreadPoolExecutor behavior
#     assert mock_thread_pool_executor.call_args[1]["max_workers"] == 5


# Create mock scanner classes
class MockScanner:
    def scan(self, session):
        # Return mock resources for the scanner
        return [{"resource_id": "resource_1"}, {"resource_id": "resource_2"}]

class AnotherMockScanner:
    def scan(self, session):
        # Return mock resources for the second scanner
        return [{"resource_id": "resource_3"}]

# Mock the get_scanner method to return the mock scanners
def mock_get_scanner(scanner_label):
    # Map scanner names to the appropriate mock classes
    scanner_map = {
        "mock_scanner": MockScanner,
        "another_mock_scanner": AnotherMockScanner,
        "Scanner1": MockScanner,  # Return MockScanner for Scanner1
        "Scanner2": AnotherMockScanner,  # Return AnotherMockScanner for Scanner2
    }
    return scanner_map.get(scanner_label, None)  # Return None if the scanner label is unknown

@patch("time.sleep", return_value=None)  # Mocking sleep to avoid actual delays during testing
@patch("scanner.resource_scanner_registry.ResourceScannerRegistry.get_scanner", side_effect=mock_get_scanner)  # Mocking the scanner registry
def test_scan_metrics(mock_sleep, mock_registry, executor, mock_session_manager):
    """Test that scan metrics are calculated correctly."""
    
    # Manually set the start_time and end_time for the test
    executor.start_time = time.time()
    executor.end_time = executor.start_time + 120  # 2 minutes from the current time
    
    # Manually set total_scans for testing
    executor.total_scans = 50
    
    # Mock regions to ensure some scanning takes place
    mock_session_manager.assume_destination_role_in_all_accounts.return_value = [
        MagicMock(get_account_id=MagicMock(return_value="123456789012"), get_regions=MagicMock(return_value=["us-east-1"]))
    ]
    
    # Manually mock the scanners
    mock_scanners = ["Scanner1", "Scanner2"]  # Use Scanner1 and Scanner2 for this test
    
    # Act: Run the execute method with the mocked scanners
    results = executor.execute()
    
    # Assert that scan metrics are calculated correctly
    assert executor.scan_metrics["total_scans"] == 52  # 50 from manual + 2 from mock scanners
    #assert executor.scan_metrics["total_run_time"] == 120  # 2 minutes = 120 seconds
    assert executor.scan_metrics["avg_scans_per_second"] > 0