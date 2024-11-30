import pytest
from unittest.mock import MagicMock, patch, call
from collections import defaultdict
from scanner.aws.account_scanner import AWSAccountScanner
from scanner.aws.session_manager import AWSSessionManager
from scanner.resource_scanner_registry import ResourceScannerRegistry


@pytest.fixture
def mock_session_manager():
    """
    Fixture to create a mock instance of AWSSessionManager.
    """
    session_manager = MagicMock(spec=AWSSessionManager)
    session_manager.switch_region = MagicMock(side_effect=lambda region, account_id: f"mocked-session-{region}")
    return session_manager


@pytest.fixture
def aws_account_scanner(mock_session_manager):
    """
    Fixture to initialize AWSAccountScanner with mocked dependencies.
    """
    return AWSAccountScanner(session_manager=mock_session_manager)


@pytest.fixture
def mock_boto_session():
    """
    Fixture to mock a boto3 session object.
    """
    session = MagicMock()
    session.switch_region = MagicMock()
    return session


@pytest.fixture
def mock_scanners():
    """
    Fixture to mock resource scanners registered in ResourceScannerRegistry.
    """
    scanner1 = MagicMock()
    scanner1.scan = MagicMock(return_value=["resource1", "resource2"])
    scanner2 = MagicMock()
    scanner2.scan = MagicMock(return_value=["resource3", "resource4"])
    return {"Scanner1": scanner1, "Scanner2": scanner2}

@patch("scanner.resource_scanner_registry.ResourceScannerRegistry.get_scanner")
def test_scan_resources_success(mock_get_scanner, aws_account_scanner, mock_boto_session):
    """
    Test that scan_resources successfully scans resources across multiple regions and scanners.
    """
    # Arrange
    account_id = "123456789012"
    regions = ["us-east-1", "us-west-2"]
    scanners = ["Scanner1", "Scanner2"]

    # Mock scanner classes and their instances
    mock_scanner1_class = MagicMock()
    mock_scanner2_class = MagicMock()
    mock_scanner1_instance = MagicMock()
    mock_scanner2_instance = MagicMock()

    # Mock scanner instance behavior
    mock_scanner1_class.return_value = mock_scanner1_instance
    mock_scanner2_class.return_value = mock_scanner2_instance
    mock_scanner1_instance.scan.return_value = ["resource1", "resource2"]
    mock_scanner2_instance.scan.return_value = ["resource3", "resource4"]

    # Mock get_scanner to return scanner classes
    mock_get_scanner.side_effect = lambda label: {
        "Scanner1": mock_scanner1_class,
        "Scanner2": mock_scanner2_class
    }[label]

    # Act
    results = aws_account_scanner.scan_resources(
        session=mock_boto_session, account_id=account_id, regions=regions, scanners=scanners
    )

    # Convert defaultdict to dict for comparison
    def normalize_defaultdict(d):
        if isinstance(d, defaultdict):
            return {k: normalize_defaultdict(v) for k, v in d.items()}
        return d

    normalized_results = normalize_defaultdict(results)

    # Expected results
    expected_results = {
        "account_id": account_id,
        "regions": regions,
        "scan_results": {
            "us-east-1": {
                "Scanner1": ["resource1", "resource2"],
                "Scanner2": ["resource3", "resource4"],
            },
            "us-west-2": {
                "Scanner1": ["resource1", "resource2"],
                "Scanner2": ["resource3", "resource4"],
            },
        },
    }

    # Assert
    assert normalized_results == expected_results

    # Verify scanner calls
    mock_scanner1_instance.scan.assert_called()
    mock_scanner2_instance.scan.assert_called()


@patch("scanner.resource_scanner_registry.ResourceScannerRegistry.get_scanner")
def test_scan_resources_scanner_not_found(mock_get_scanner, aws_account_scanner, mock_boto_session):
    """
    Test scan_resources when a scanner label does not exist in the registry.
    """
    # Arrange
    account_id = "123456789012"
    regions = ["us-east-1"]
    scanners = ["NonExistentScanner"]

    mock_get_scanner.return_value = None

    # Act
    results = aws_account_scanner.scan_resources(
        session=mock_boto_session, account_id=account_id, regions=regions, scanners=scanners
    )

    # Assert
    assert results["scan_results"]["us-east-1"] == {}


@patch("scanner.resource_scanner_registry.ResourceScannerRegistry.get_scanner")
def test_scan_resources_switch_region_error(mock_get_scanner, aws_account_scanner, mock_boto_session):
    """
    Test scan_resources when an error occurs while switching regions.
    """
    # Arrange
    account_id = "123456789012"
    regions = ["us-east-1", "invalid-region"]
    scanners = ["Scanner1"]

    mock_get_scanner.side_effect = lambda label: MagicMock(scan=MagicMock(return_value=["resource1"]))
    mock_boto_session.switch_region.side_effect = lambda region, account_id: (
        Exception("Region switch failed") if region == "invalid-region" else f"mocked-session-{region}"
    )

    # Act
    results = aws_account_scanner.scan_resources(
        session=mock_boto_session, account_id=account_id, regions=regions, scanners=scanners
    )

    # Assert
    assert "invalid-region" not in results["scan_results"]
    mock_boto_session.switch_region.assert_any_call("us-east-1", account_id)


@patch("scanner.resource_scanner_registry.ResourceScannerRegistry.get_scanner")
def test_scan_resources_scanner_error(mock_get_scanner, aws_account_scanner, mock_boto_session):
    """
    Test scan_resources when a scanner raises an exception during scanning.
    """
    # Arrange
    account_id = "123456789012"
    regions = ["us-east-1"]
    scanners = ["FaultyScanner"]

    faulty_scanner = MagicMock()
    faulty_scanner.scan.side_effect = Exception("Scanner error")
    mock_get_scanner.return_value = faulty_scanner

    # Act
    results = aws_account_scanner.scan_resources(
        session=mock_boto_session, account_id=account_id, regions=regions, scanners=scanners
    )

    # Assert
    assert results["scan_results"]["us-east-1"] == {"FaultyScanner": []}


def test_aws_account_scanner_initialization(mock_session_manager):
    """
    Test that AWSAccountScanner initializes correctly.
    """
    scanner = AWSAccountScanner(session_manager=mock_session_manager)
    assert scanner.session_manager == mock_session_manager
