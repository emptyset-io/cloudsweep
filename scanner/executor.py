from concurrent.futures import ThreadPoolExecutor, as_completed
from scanner.aws.account_scanner import AWSAccountScanner
from scanner.aws.session_manager import AWSSessionManager
from utils.logger import get_logger
import os
import time

logger = get_logger(__name__)

class Executor:
    def __init__(self, session: AWSSessionManager, scanners: list = [], regions: list = [], max_workers: int = 10):
        self.session = session
        self.regions = regions
        self.scanners = scanners
        self.max_workers = max_workers
        if not self.max_workers:
            self.max_workers = (os.cpu_count() - 1)

        # Initialize metrics
        self.total_scans = 0
        self.start_time = None
        self.end_time = None
        self.scan_metrics = {}

    def execute(self):
        logger.info(f"Starting scan execution...")
        
        # Start tracking time
        self.start_time = time.time()

        # Assume roles for all accounts
        logger.debug("Assuming roles for all accounts...")
        sessions = self.session.assume_destination_role_in_all_accounts()

        logger.info(f"Retrieved {len(sessions)} sessions for scanning.")
        logger.debug(f"Scanners to be used: {self.scanners}")

        scanner = AWSAccountScanner(self.session)

        # Using ThreadPoolExecutor for account-region-scanner parallelism
        results = []
        logger.debug(f"Using {self.max_workers} Threads")
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            for session in sessions:
                account_id = session.get_account_id()
                regions = self._get_regions_for_session(session)
                logger.info(f"Regions for scanning: {regions}")
                for scanner_name in self.scanners:
                    if scanner_name == 'iam':
                        # Only scan IAM once per account (using the 'Global' region)
                        futures.append(
                            executor.submit(self._scan_region_scanner, scanner, session, account_id, 'Global', scanner_name)
                        )
                    else:
                        # Scan all regions for non-IAM resource types
                        for region in regions:
                            futures.append(
                                executor.submit(self._scan_region_scanner, scanner, session, account_id, region, scanner_name)
                            )

            logger.debug(f"Submitted {len(futures)} scanning tasks to executor.")

            # Collect and process results
            for future in as_completed(futures):
                try:
                    result = future.result()  # This will re-raise exceptions if any occurred
                    if result:
                        results.append(result)
                        # Update scan metrics
                        self.total_scans += 1
                except Exception as e:
                    logger.error(f"Error during scan execution: {e}")

        # End time
        self.end_time = time.time()
        logger.info("Scan execution completed.")

        # Calculate total run time and average scans per second
        total_run_time = self.end_time - self.start_time
        avg_scans_per_second = self.total_scans / total_run_time if total_run_time > 0 else 0

        # Store metrics in the instance
        self.scan_metrics = {
            "total_scans": self.total_scans,
            "avg_scans_per_second": round(avg_scans_per_second, 2),
            "total_run_time": round(total_run_time, 2),
        }

        return results

    def _get_regions_for_session(self, session):
        """
        Determine the regions to process for the given session.
        """
        if self.regions == "all" or not self.regions:
            return session.get_regions()
        return [region for region in session.get_regions() if region in self.regions]

    def _scan_region_scanner(self, scanner, session, account_id, region, scanner_name):
        """
        Perform a scan for a specific scanner in a specific region.

        :param scanner: AWSAccountScanner instance.
        :param session: Authenticated AWS session for the account.
        :param account_id: The ID of the AWS account.
        :param region: The region to scan (for IAM, region will be 'Global').
        :param scanner_name: The scanner to execute.
        :return: Scan result for the specific scanner and region.
        """
        try:
            result = scanner.scan_resources(session, account_id, [region], [scanner_name])
            return result
        except Exception as e:
            logger.error(f"Error scanning account {account_id} in region {region} with scanner {scanner_name}: {e}")
            return None
