import argparse
from utils.logger import get_logger
import os
import sys
from scanner.resource_scanner_registry import ResourceScannerRegistry

logger = get_logger(__name__)

class ArgumentParser:
    """
    Class for parsing and managing command-line arguments for the AWS Scanner CLI.
    """

    @staticmethod
    def parse_arguments():
        """
        Parse command-line arguments.
        """
        parser = argparse.ArgumentParser(description="AWS Scanner CLI")
        parser.add_argument("--organization-role", help="IAM Role Name for querying the organization.")
        parser.add_argument("--runner-role", help="IAM Role Name for scanning organization accounts.")
        parser.add_argument("--profile", help="AWS profile to use.")
        parser.add_argument("--list-scanners", action="store_true", help="List all available scanners.")
        parser.add_argument("--all-scanners", action="store_true", help="Use all scanners.")
        parser.add_argument("--scanners", help="Comma-separated list of scanners.")
        parser.add_argument("--regions", help="Comma-separated list of regions.")
        parser.add_argument("--all-regions", action="store_true", help="Scan all regions.")
        parser.add_argument("--max-workers", type=int, default=(os.cpu_count() - 1),
                            help="Maximum number of workers to use (default: one less than the number of CPUs).")
        
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
        
        if args.all_scanners:
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
            # Default to all scanners
            scanners = all_scanners
        
        return scanners

    @staticmethod
    def get_regions(args):
        """
        Determine which regions to use based on arguments.
        """
        if args.all_regions:
            logger.info("Using all regions for the scan.")
            return "all"  # Process all regions
        elif args.regions:
            regions = args.regions.split(",")
            logger.info(f"Using specified regions: {regions}")
            return regions
        else:
            logger.info("No specific regions or 'all-regions' flag provided. Defaulting to all regions.")
            return "all"

    @staticmethod
    def get_max_workers(args):
        """
        Get the maximum number of workers from the arguments.
        """
        max_workers = args.max_workers
        logger.info(f"Using {max_workers} worker(s).")
        return max_workers
