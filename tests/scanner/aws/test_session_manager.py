import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
from scanner.aws.session_manager import AWSSessionManager

# Mock session and AWS responses
@pytest.fixture
def mock_session():
    with patch("boto3.Session") as MockSession:
        session = MockSession.return_value
        session.client.return_value = MagicMock()
        yield session

@pytest.fixture
def session_manager():
    """Fixture to initialize AWSSessionManager."""
    return AWSSessionManager(profile_name="test-profile")

@pytest.fixture
def mock_logger():
    with patch('scanner.aws.session_manager.logger') as mock:
        yield mock

@patch("boto3.Session")  # Patch boto3.Session
def test_get_session(mock_boto3_session):
    """Test session creation."""
    # Arrange: Mock the boto3.Session instance
    mock_session = MagicMock()
    mock_boto3_session.return_value = mock_session

    # Create an instance of AWSSessionManager with a test profile
    session_manager = AWSSessionManager(profile_name="test-profile")

    # Act: Call get_session
    session = session_manager.get_session()

    # Assert: Verify the session is the mocked session
    assert session == mock_session

    # Verify that boto3.Session was called with the expected parameters
    mock_boto3_session.assert_called_once_with(profile_name="test-profile", region_name=None)
    mock_boto3_session.assert_called_once_with(profile_name="test-profile", region_name=None)


def test_get_account_id(mock_session, session_manager):
    """Test retrieving account ID."""
    mock_sts_client = mock_session.client.return_value
    mock_sts_client.get_caller_identity.return_value = {"Account": "123456789012"}
    
    account_id = session_manager.get_account_id()
    assert account_id == "123456789012"
    mock_session.client.assert_called_with("sts")
    mock_sts_client.get_caller_identity.assert_called_once()

def test_get_account_id_client_error(mock_session, session_manager):
    """Test account ID retrieval with a ClientError."""
    mock_sts_client = mock_session.client.return_value
    mock_sts_client.get_caller_identity.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, 
        "GetCallerIdentity"
    )
    
    with pytest.raises(ClientError):
        session_manager.get_account_id()
@patch("boto3.Session")
def test_assume_role_success(mock_boto3_session, mock_logger):
    # Arrange: Mock the boto3.Session instance and sts client
    mock_session = MagicMock()
    mock_boto3_session.return_value = mock_session
    mock_sts_client = mock_session.client.return_value

    # Mock the assume_role response
    mock_sts_client.assume_role.return_value = {
        "Credentials": {
            "AccessKeyId": "mock_access_key",
            "SecretAccessKey": "mock_secret_key",
            "SessionToken": "mock_session_token",
        }
    }

    # Mock get_credentials() method to return mocked credentials
    mock_credentials = MagicMock()
    mock_credentials.access_key = "mock_access_key"
    mock_credentials.secret_key = "mock_secret_key"
    mock_credentials.token = "mock_session_token"
    mock_session.get_credentials.return_value = mock_credentials

    # Create the instance of AWSSessionManager
    session_manager = AWSSessionManager(profile_name="test-profile")

    # Act: Call assume_role to assume the role
    assumed_session_manager = session_manager.assume_role(
        role_name="test-role",
        account_id="123456789012"
    )

    # Assert: Check that the returned session has the expected credentials
    assert assumed_session_manager._session.get_credentials().access_key == "mock_access_key"
    assert assumed_session_manager._session.get_credentials().secret_key == "mock_secret_key"
    assert assumed_session_manager._session.get_credentials().token == "mock_session_token"

    # Assert: Ensure that assume_role was called correctly
    mock_sts_client.assume_role.assert_called_once_with(
        RoleArn="arn:aws:iam::123456789012:role/test-role",
        RoleSessionName="AWSScannerSession"
    )

# Test case: Role assumption fails due to ClientError


@patch("boto3.Session")
def test_assume_role_failure(mock_boto3_session, mock_logger):
    # Arrange: Mock the boto3.Session instance and sts client
    mock_session = MagicMock()
    mock_boto3_session.return_value = mock_session
    mock_sts_client = mock_session.client.return_value

    # Mock the assume_role to raise a ClientError
    mock_sts_client.assume_role.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "AssumeRole"
    )

    # Create the instance of AWSSessionManager
    session_manager = AWSSessionManager(profile_name="test-profile")

    # Act & Assert: Ensure that ClientError is raised when assuming the role
    with pytest.raises(ClientError):
        session_manager.assume_role(
            role_name="test-role",
            account_id="123456789012"
        )

    # Assert: Ensure the error is logged correctly
    mock_logger.error.assert_called_once_with(
        "Error assuming role test-role in account 123456789012: An error occurred (AccessDenied) when calling the AssumeRole operation: Access Denied"
    )

@patch("boto3.Session")
def test_get_regions(mock_boto3_session):
    """Test retrieving regions."""
    # Arrange: Mock the boto3.Session instance and EC2 client
    mock_session = MagicMock()
    mock_boto3_session.return_value = mock_session
    mock_ec2_client = mock_session.client.return_value

    # Mock the describe_regions response
    mock_ec2_client.describe_regions.return_value = {
        "Regions": [
            {"RegionName": "us-east-1"},
            {"RegionName": "us-west-1"},
        ]
    }
    
    # Create the AWSSessionManager instance
    session_manager = AWSSessionManager(profile_name="test-profile")
    
    # Act: Call get_regions (it will use mock_session internally)
    regions = session_manager.get_regions()
    
    # Assert: Verify that the regions are correctly retrieved
    assert regions == ["us-east-1", "us-west-1"]

@patch("boto3.Session")
def test_get_organization_accounts(mock_boto3_session):
    """Test retrieving organization accounts."""
    
    # Mock session and clients
    mock_session = MagicMock()
    mock_boto3_session.return_value = mock_session
    
    # Mock sts client
    mock_sts_client = MagicMock()
    mock_sts_client.get_caller_identity.return_value = {"Account": "123456789012"}
    
    # Mock organizations client
    mock_org_client = MagicMock()
    mock_paginator = MagicMock()
    mock_org_client.get_paginator.return_value = mock_paginator
    
    # Mock the pagination to return accounts in multiple pages
    mock_paginator.paginate.return_value = [
        {"Accounts": [{"Id": "123456789012", "Status": "ACTIVE"}]},
        {"Accounts": [{"Id": "987654321098", "Status": "ACTIVE"}]}
    ]
    
    # Mock ec2 client (even though it's not directly used in this test, it's called internally)
    mock_ec2_client = MagicMock()
    
    # Configure mock_session.client to return the appropriate client
    def client_side_effect(service_name, *args, **kwargs):
        if service_name == "sts":
            return mock_sts_client
        elif service_name == "organizations":
            return mock_org_client
        elif service_name == "ec2":
            return mock_ec2_client
        else:
            raise ValueError(f"Unexpected service name: {service_name}")
    
    mock_session.client.side_effect = client_side_effect
    
    # Initialize session manager with mocked session
    session_manager = AWSSessionManager(
        profile_name="test-profile",
        organization_role="OrganizationAccountAccessRole"
    )
    
    # Act: Call get_organization_accounts to retrieve the accounts
    accounts = session_manager.get_organization_accounts()

    # Assert: Ensure the accounts list matches the expected data
    assert accounts == [{"Id": "123456789012", "Status": "ACTIVE"}, {"Id": "987654321098", "Status": "ACTIVE"}]

@patch("boto3.Session")
def test_switch_region(mock_boto3_session):
    """Test switching regions."""
    # Mock credentials
    mock_credentials = MagicMock()
    mock_credentials.access_key = "mock_access_key"
    mock_credentials.secret_key = "mock_secret_key"
    mock_credentials.token = "mock_session_token"
    
    # Mock session
    mock_session = MagicMock()
    mock_session.get_credentials.return_value.get_frozen_credentials.return_value = mock_credentials
    mock_boto3_session.return_value = mock_session
    
    # Set the region_name directly for the mock session
    mock_session.region_name = "us-west-1"
    
    # Initialize session manager
    session_manager = AWSSessionManager(profile_name="test-profile")
    session_manager._session = mock_session
    
    # Act: Call switch_region with both region_name and account_id
    new_session = session_manager.switch_region("us-west-1", "123456789012")  # Include account_id
    
    # Assertions
    assert new_session.region_name == "us-west-1"  # Check that region_name is correctly set on the mock session

# Additional Tests for Error Handling
def test_assume_role_error(mock_session, session_manager):
    """Test assume role with error handling."""
    mock_sts_client = mock_session.client.return_value
    mock_sts_client.assume_role.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, 
        "AssumeRole"
    )
    
    with pytest.raises(ClientError):
        session_manager.assume_role(role_name="invalid-role", account_id="123456789012")

