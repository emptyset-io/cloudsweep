#!/usr/bin/env python
import time
import encodings.idna
from scanner.executor import Executor
from scanner.aws.session_manager import AWSSessionManager
from utils.logger import get_logger
from reports.html.report_generator import generate_html_report
from scanner.argument_parser import ArgumentParser
from scanner.resource_scanner_registry import ResourceScannerRegistry
logger = get_logger(__name__)

def main():
    try:
        # Load Scanners
        ResourceScannerRegistry.register_scanners_from_directory("scanner/aws/services")
        # Parse arguments
        args = ArgumentParser.parse_arguments()
        logger.debug(f"Parsed arguments: {args}")

        # Handle scanners and regions
        scanners = ArgumentParser.get_scanners(args)
        regions = ArgumentParser.get_regions(args)

        # Initialize session manager with the provided profile and roles
        logger.info(f"Using AWS profile: {args.profile}")
        session_manager = AWSSessionManager(
            profile_name=args.profile,
            organization_role=args.organization_role,
            runner_role=args.runner_role,
        )
        # Initialize and execute the scan
        executor = Executor(session=session_manager, scanners=scanners, regions=regions, max_workers=args.max_workers)
        scan_results, scan_metrics = executor.execute()

        report_filename = generate_html_report(
            scan_results=scan_results,
            start_time=scan_metrics["start_time"],
            scan_metrics=scan_metrics
        )
        logger.debug(f"Report successfully generated: {report_filename}")
    except Exception as e:
        logger.exception(f"An error occurred: {e}")



if __name__ == "__main__":
    main()