import argparse
import os
import sys
from utils.logger import get_logger
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
        parser.add_argument("--profile", default=os.getenv("CS_AWS_PROFILE"), help="AWS profile to use.")
        parser.add_argument("--list-scanners", action="store_true", help="List all available scanners.")
        parser.add_argument("--all-scanners", action="store_true", help="Use all scanners.")
        parser.add_argument("--scanners", default=os.getenv("CS_SCANNERS", "all"), help="Comma-separated list of scanners or 'all' to use all scanners.")
        parser.add_argument("--regions", default=os.getenv("CS_REGIONS", "all"), help="Comma-separated list of regions or 'all' to use all regions.")
        parser.add_argument("--max-workers", type=int, default=int(os.getenv("CS_MAX_WORKERS", os.cpu_count() - 1)), help="Maximum number of workers to use (default: one less than the number of CPUs).")
        
        # New argument for days-threshold
        parser.add_argument("--days-threshold", type=int, default=int(os.getenv("CS_DAYS_THRESHOLD", 90)), help="The number of days to look back at resource metrics and history to determine if something is unused (default: 90 days).")

        args = parser.parse_args()
    
        # If no critical arguments are passed, handle it gracefully
        if not (args.organization_role or args.runner_role or args.profile or args.list_scanners or args.all_scanners):
            parser.print_help()
            sys.exit(1)

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
        
        # Handle 'all' value for scanners
        if args.scanners == "all" or args.all_scanners:
            scanners = all_scanners  # Use all available scanners
            logger.info("Using all scanners.")
        elif args.scanners:
            # Use specific scanners from the user's input
            requested_scanners = args.scanners.split(",")
            scanners = []

            # Validate each requested scanner
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
            # Default to all scanners if no specific scanners are provided
            scanners = all_scanners
        
        return scanners

    @staticmethod
    def get_regions(args):
        """
        Determine which regions to use based on arguments.
        """
        if args.regions == "all":
            logger.info("Using all regions for the scan.")
            return "all"  # Process all regions
        elif args.regions:
            regions = args.regions.split(",")
            logger.info(f"Using specified regions: {regions}")
            return regions
        else:
            logger.info("No specific regions provided. Defaulting to all regions.")
            return "all"

    @staticmethod
    def get_max_workers(args):
        """
        Get the maximum number of workers from the arguments.
        """
        max_workers = args.max_workers
        logger.info(f"Using {max_workers} worker(s).")
        return max_workers

    @staticmethod
    def get_days_threshold(args):
        """
        Get the days threshold from the arguments or environment variable.
        """
        days_threshold = args.days_threshold
        logger.info(f"Using {days_threshold} days as the threshold to identify unused resources.")
        return days_threshold
