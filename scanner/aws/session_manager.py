import boto3
from concurrent.futures import ThreadPoolExecutor, as_completed
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
from utils.logger import get_logger
import os

logger = get_logger(__name__)

class AWSSessionManager:
    """
    Manages AWS sessions, including assuming roles, switching regions, and creating new sessions.
    """

    def __init__(self, profile_name: str = "default", account_id: str = None, organization_role: str = None, runner_role: str = None):
        """
        Initialize the AWS session manager.

        Args:
            profile_name (str): AWS profile name.
            organization_role (str): The role name to assume within the organization (optional).
            runner_role (str): The role name used for running tasks (optional).
        """
        logger.debug(f"Initializing AWSSessionManager with profile_name={profile_name}, account_id={account_id}, organization_role={organization_role}, runner_role={runner_role}")
        self.profile_name = profile_name
        self.region_name = None
        self.runner_role = runner_role
        self.organization_role = organization_role
        self.account_id = account_id
        self._session = None
        self._organization_session = None
        self.account_id = None


        self.regions = self.get_regions()
        logger.debug(f"Regions: {self.regions}")

        if self.organization_role:
            logger.debug(f"Automatically assuming organization role {self.organization_role}")
            self._organization_session = self.assume_role(self.organization_role, self.get_account_id())

    def get_session(self) -> boto3.Session:
        """
        Get or create a boto3 session.

        Returns:
            boto3.Session: The created session.
        """
        if not self._session:
            try:
                logger.debug(f"Creating AWS session with profile_name={self.profile_name}")
                self._session = boto3.Session(
                    profile_name=self.profile_name,
                    region_name=self.region_name
                )
                logger.debug("AWS session created successfully")
            except (NoCredentialsError, PartialCredentialsError) as e:
                logger.error(f"Failed to create AWS session: {e}")
                raise
        else:
            logger.debug("Using existing AWS session.")
        return self._session

    def get_account_id(self) -> str:
        """
        Retrieve the AWS Account ID using the STS client.

        Returns:
            str: AWS Account ID.
        """
        session = self.get_session()
        try:
            sts_client = session.client('sts')
            response = sts_client.get_caller_identity()
            logger.info(f"Retrieved Account ID: {response['Account']}")
            self.account_id = response['Account']
            return response['Account']
        except ClientError as e:
            logger.error(f"Error retrieving account ID: {e}")
            raise

    def get_regions_by_session(self, session: "AWSSessionManager") -> dict:
        """
        Retrieves the regions associated with the provided session.

        Args:
            session (AWSSessionManager): The session manager instance to use.

        Returns:
            dict: A dictionary with the assumed session and regions.
        """
        try:
            regions = session.get_regions()
            account_id = self.get_account_id()
            return {account_id: (session, regions)}

        except Exception as e:
            logger.error(f"Error retrieving regions: {e}")
            raise

    def assume_role(self, role_name: str, account_id: str, session_name="AWSScannerSession", session: "AWSSessionManager" = None) -> "AWSSessionManager":
        """
        Assume a role in a specific account and return a new AWSSessionManager with the assumed role credentials.

        Args:
            role_name (str): Role name to assume.
            account_id (str): AWS account ID where the role resides.
            session_name (str): Session name for the assumed role session (default: AWSScannerSession).
            session (AWSSessionManager, optional): An optional AWSSessionManager instance to use for assuming the role.

        Returns:
            AWSSessionManager: A new AWSSessionManager instance with assumed role credentials.
        """
        try:
            if session:
                sts_client = session.get_session().client('sts')
            else:
                sts_client = self.get_client("sts")

            role_arn = self.resolve_role_arn(role_name, account_id)

            # Assume the role using STS
            response = sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName=session_name
            )
            logger.debug(f"Assumed role {role_name} successfully, receiving credentials.")
            
            # Extract credentials from the assume_role response
            credentials = response['Credentials']

            # Create a new AWSSessionManager instance with the assumed role credentials
            new_session = boto3.Session(
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken']
            )
            new_manager = AWSSessionManager(profile_name=self.profile_name)
            new_manager._session = new_session
            return new_manager

        except ClientError as e:
            logger.error(f"Error assuming role {role_name} in account {account_id}: {e}")
            raise

    def get_regions(self) -> list[str]:
        """
        Get a list of AWS regions for the current session.

        Returns:
            list[str]: List of region names.
        """
        logger.debug(f"Getting regions for assumed session: {self._session}")
        ec2_client = self.get_client("ec2")
        response = ec2_client.describe_regions()
        regions = [region['RegionName'] for region in response['Regions']]
        logger.debug(f"Regions retrieved: {regions}")
        return regions

    def get_organization_accounts(self) -> list:
        """
        Get the list of fully added accounts in the AWS Organization.

        Returns:
            list: A list of active account details.
        """
        try:
            logger.debug("Getting organization accounts")

            if not self._organization_session:
                if not self.organization_role:
                    raise ValueError(
                        "Organization role is required to get organization accounts but was not provided."
                    )
                logger.debug(f"Assuming organization role: {self.organization_role}")
                account_id = self.get_account_id()
                self._organization_session = self.assume_role(
                    role_name=self.organization_role,
                    account_id=account_id,
                    session_name="OrganizationSession"
                )

            org_client = self._organization_session.get_session().client("organizations")

            # Retrieve accounts with pagination
            accounts = []
            paginator = org_client.get_paginator("list_accounts")
            for page in paginator.paginate():
                accounts.extend(page["Accounts"])

            # Filter accounts by status
            active_accounts = [account for account in accounts if account["Status"] == "ACTIVE"]

            logger.debug(f"Active organization accounts retrieved: {active_accounts}")
            return active_accounts

        except ValueError as ve:
            logger.error(f"Configuration error: {ve}")
            raise
        except Exception as e:
            logger.error(f"Error getting AWS organization accounts: {e}")
            raise

    def get_account_name(account_list, account_id):
        """
        Retrieve the account name for a given account ID from the account list.

        Args:
            account_list (list): A list of dictionaries containing 'Id' and 'Name' keys.
            account_id (str): The account ID to look up.

        Returns:
            str: The name of the account corresponding to the given account ID.
                Returns None if the account ID is not found.
        """
        for account in account_list:
            if account["Id"] == account_id:
                return account["Name"]
        return None  # Return None if the account ID is not found


    def assume_destination_role_in_all_accounts(self) -> list:
        """
        Assume the destination role across all accounts within the organization and return a list of AWSSessionManager instances.

        Args:
            destination_role (str): The role name in the destination account.

        Returns:
            list: A list of assumed AWSSessionManager instances for each account.
        """
        try:
            logger.debug(f"Assuming destination role {self.runner_role} in all accounts")
            org_accounts = self.get_organization_accounts()
            assumed_sessions = []

            # Determine max workers based on available CPU cores
            max_workers = os.cpu_count() - 1

            # Use ThreadPoolExecutor to assume roles concurrently
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [
                    executor.submit(self._assume_role_for_account, account)
                    for account in org_accounts
                ]

                # Process results as they complete
                for future in as_completed(futures):
                    try:
                        assumed_session = future.result()
                        if assumed_session:
                            assumed_sessions.append(assumed_session)
                    except Exception as e:
                        logger.error(f"Error assuming role for an account: {e}")
            
            return assumed_sessions

        except Exception as e:
            logger.error(f"Error assuming destination role in all accounts: {e}")
            raise

    def _assume_role_for_account(self, account):
        """
        Helper method to assume a role for a specific account.

        Args:
            account (dict): The account information (e.g., account ID)

        Returns:
            AWSSessionManager: The assumed session manager instance
        """
        account_id = account['Id']
        logger.debug(f"Assuming destination role in account {account_id}")
        try:
            # Try to assume the role for the current account
            return self.assume_role(
                role_name=self.runner_role,
                account_id=account_id,
                session_name="CustomSessionName",
                session=self._organization_session
            )
        except Exception as e:
            logger.error(f"Error assuming destination role for account {account_id}: {e}")
            return None


    def get_client(self, service_name: str) -> boto3.client:
        """
        Get a boto3 client for a specified AWS service using the current session.

        Args:
            service_name (str): The AWS service name (e.g., 'sts', 'ec2').

        Returns:
            boto3.client: The AWS service client.
        """
        logger.debug(f"Getting client for service: {service_name}")
        session = self.get_session()
        return session.client(service_name)

    def resolve_role_arn(self, role_name: str, account_id: str) -> str:
        """
        Resolve the full ARN of a role given its name and the target account ID.

        Args:
            role_name (str): Role name.
            account_id (str): Target AWS account ID.

        Returns:
            str: Full ARN of the role.
        """
        arn = f"arn:aws:iam::{account_id}:role/{role_name}"
        logger.debug(f"Resolved role ARN: {arn}")
        return arn

    def switch_region(self, new_region_name: str, account_id: int) -> "AWSSessionManager":
        """
        Switch to a new region, preserving the current session credentials.

        Args:
            new_region_name (str): The target AWS region.

        Returns:
            AWSSessionManager: A new AWSSessionManager instance with the region switched.
        """
        logger.debug(f"Switching region to {new_region_name}")
        session = self.get_session()
        credentials = session.get_credentials().get_frozen_credentials()
        
        # Ensure that the region_name is being passed correctly
        new_session = boto3.Session(
            aws_access_key_id=credentials.access_key,
            aws_secret_access_key=credentials.secret_key,
            aws_session_token=credentials.token,
            region_name=new_region_name
        )
        
        # Create a new manager and set the region
        new_manager = AWSSessionManager(profile_name=self.profile_name, account_id=account_id)
        new_manager._session = new_session
        new_manager.region_name = new_region_name  # Ensure region is stored
        logger.debug("Region switched successfully.")
        
        return new_manager