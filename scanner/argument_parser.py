import argparse
import os
import sys
from utils.logger import get_logger
from scanner.aws.session_manager import AWSSessionManager
from scanner.resource_scanner_registry import ResourceScannerRegistry

logger = get_logger(__name__)

class ArgumentParser:
    """
    Class for parsing and managing command-line arguments for the AWS Scanner CLI.
    """

    @staticmethod
    def parse_arguments():
        """
        Parse command-line arguments, with support for environment variables.
        """
        parser = argparse.ArgumentParser(description="AWS Scanner CLI")
        
        # Command-line arguments
        parser.add_argument("--organization-role", default=os.getenv("CS_ORGANIZATION_ROLE"), help="IAM Role Name for querying the organization.")
        parser.add_argument("--runner-role", default=os.getenv("CS_RUNNER_ROLE"), help="IAM Role Name for scanning organization accounts.")
        parser.add_argument("--list-scanners", action="store_true", help="List all available scanners.")
        parser.add_argument("--list-accounts", action="store_true", help="List all accounts in the AWS Organization.")
        parser.add_argument("--accounts", default=os.getenv("CS_ACCOUNTS", "all"), help="Comma-separated list of account IDs or 'all' for all accounts.")
        parser.add_argument("--scanners", default=os.getenv("CS_SCANNERS", "all"), help="Comma-separated list of scanners or 'all' to use all scanners.")
        parser.add_argument("--regions", default=os.getenv("CS_REGIONS", "all"), help="Comma-separated list of regions or 'all' to use all regions.")
        parser.add_argument("--max-workers", type=int, default=int(os.getenv("CS_MAX_WORKERS", os.cpu_count() - 1)), help="Maximum number of workers to use (default: one less than the number of CPUs).")
        parser.add_argument("--days-threshold", type=int, default=int(os.getenv("CS_DAYS_THRESHOLD", 90)), help="The number of days to look back at resource metrics and history to determine if something is unused (default: 90 days).")
        parser.add_argument("--upload-confluence", action="store_true", default=False, help="Set to True if you want to upload reports to Confluence.")

        args = parser.parse_args()

        return args

    @staticmethod
    def get_scanners(args):
        """
        Determine which scanners to use based on arguments.
        """
        all_scanners = ResourceScannerRegistry.list_scanners()
        
        if args.list_scanners:
            print("Available Scanners:")
            for scanner_name in all_scanners:
                print(scanner_name)
            sys.exit(0)  # Exit point for list mode
        
        if args.scanners == "all":
            scanners = all_scanners  # Use all available scanners
            logger.debug("Using all scanners.")
        elif args.scanners:
            requested_scanners = args.scanners.split(",")
            scanners = []

            for scanner_name in requested_scanners:
                if ResourceScannerRegistry.get_scanner(scanner_name):
                    scanners.append(scanner_name)
                    logger.debug(f"Using specified scanner: {scanner_name}")
                else:
                    print(f"Scanner '{scanner_name}' is invalid or not found.")
                    print("Available Scanners:")
                    for scanner_name in all_scanners:
                        print(scanner_name)
                    sys.exit(1)
            
            if not scanners:
                logger.error("No valid scanners were provided.")
                sys.exit(1)
        else:
            scanners = all_scanners
        
        return scanners

    @staticmethod
    def get_accounts(args, session_manager):
        """
        Determine which accounts to use based on arguments and validate against available accounts.

        Args:
            args: Parsed arguments.
            session_manager: An instance of AWSSessionManager.

        Returns:
            list: A list of dictionaries containing account 'Id' and 'Name' or 'all'.
        """
        if args.list_accounts:
            # If list_accounts flag is set, list the organization accounts
            try:
                formatted_accounts = [f"{account['Id']} - {account['Name']}" for account in session_manager.get_organization_accounts()]
                print("Available Organization Accounts:")
                for account in formatted_accounts:
                    print(account)

                sys.exit(0)  # Exit after listing accounts
            except Exception as e:
                logger.error(f"Failed to list organization accounts: {e}")
                sys.exit(1)
        
        # Get available accounts from the session manager
        available_accounts = session_manager.get_organization_accounts()
        
        if not args.accounts or args.accounts == "all":
            logger.debug("Using all accounts.")
            # Return list of dictionaries with both 'Id' and 'Name' for all accounts
            return [{"Id": account["Id"], "Name": account["Name"]} for account in available_accounts]
        
        else:
            requested_accounts = args.accounts.split(",")
            logger.debug(f"Using specified accounts: {requested_accounts}")
            
            # Validate requested accounts and return list of dictionaries with 'Id' and 'Name' for valid accounts
            valid_accounts = [
                {"Id": account["Id"], "Name": account["Name"]}
                for account in available_accounts if account["Id"] in requested_accounts
            ]
            
            if not valid_accounts:
                logger.error("No valid accounts provided or selected.")
                sys.exit(1)

            return valid_accounts



    @staticmethod
    def get_regions(args):
        """
        Determine which regions to use based on arguments.
        """
        if args.regions == "all":
            logger.debug("Using all regions for the scan.")
            return "all"
        elif args.regions:
            regions = args.regions.split(",")
            logger.debug(f"Using specified regions: {regions}")
            return regions
        else:
            logger.debug("No specific regions provided. Defaulting to all regions.")
            return "all"

    @staticmethod
    def get_max_workers(args):
        """
        Get the maximum number of workers from the arguments.
        """
        max_workers = args.max_workers
        logger.debug(f"Using {max_workers} worker(s).")
        return max_workers

    @staticmethod
    def get_days_threshold(args):
        """
        Get the days threshold from the arguments or environment variable.
        """
        days_threshold = args.days_threshold
        logger.debug(f"Using {days_threshold} days as the threshold to identify unused resources.")
        return days_threshold
