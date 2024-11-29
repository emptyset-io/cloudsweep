from collections import defaultdict
from scanner.aws.session_manager import AWSSessionManager
from scanner.resource_scanner_registry import ResourceScannerRegistry
from utils.logger import get_logger
import boto3

logger = get_logger(__name__)

class AWSAccountScanner:
    """
    A scanner for AWS accounts that retrieves and processes details about accounts and their resources.
    """

    def __init__(self, session_manager: AWSSessionManager):
        """
        Initialize the scanner with a session manager and resource scanner registry.

        :param session_manager: Instance of AWSSessionManager
        """
        self.session_manager = session_manager
        logger.info("AWSAccountScanner initialized.")

    def scan_resources(self, session, account_id, regions, scanners):
        """
        Perform the scan for each resource type based on the selected scanners across all regions.

        :param session: Boto3 session object
        :param account_id: The AWS account ID
        :param regions: List of AWS regions to scan
        :param scanners: List of scanners (strings representing scanner labels)
        :return: A dictionary of scan results
        """
        logger.info(f"Starting scan for account {account_id} in regions {regions} using scanners {scanners}")
        all_scan_results = defaultdict(list)

        # Iterate through each region
        for region in regions:
            logger.debug(f"Switching region to {region} for account {account_id}")
            try:
                # Switch the region for the session once at the start of each region's scan
                session = session.switch_region(region, account_id)
                logger.debug(f"Successfully switched to region {region}")
            except Exception as e:
                logger.error(f"Error occurred while switching region {region}: {e}")
                continue  # Skip to the next region if there's an error

            region_scan_results = defaultdict(list)

            # Iterate over the scanners provided as arguments
            for scanner_label in scanners:
                logger.debug(f"Processing scanner: {scanner_label} in region {region}")
                try:
                    # Lookup the scanner from the ResourceScannerRegistry by label
                    scanner_class = ResourceScannerRegistry.get_scanner(scanner_label)()

                    if scanner_class:
                        logger.debug(f"Running scanner for {scanner_label} in region {region}")
                        # Call the scanner's scan method (assuming scan method takes session and account_id as arguments)
                        try:
                            resources = scanner_class.scan(session)
                            region_scan_results[scanner_label].extend(resources)
                            logger.debug(f"Found {len(resources)} resources for {scanner_label} in region {region}")
                        except Exception as e:
                            logger.error(f"Error occurred while scanning with {scanner_label} in region {region}: {e}")
                    else:
                        logger.error(f"Scanner with label '{scanner_label}' not found.")
                except Exception as e:
                    logger.error(f"Error occurred while processing scanner {scanner_label} in region {region}: {e}")

            # Store the results for this region after scanning all requested resources
            all_scan_results[region] = region_scan_results
            logger.debug(f"Completed scanning for region {region}")

        logger.info(f"Completed all scans for account {account_id}")
        return {
            "account_id": account_id,
            "regions": regions,
            "scan_results": all_scan_results,
        }
