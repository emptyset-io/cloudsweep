#!/usr/bin/env python
import os
import logging
from scanner.executor import Executor
from scanner.aws.session_manager import AWSSessionManager
from scanner.argument_parser import ArgumentParser
from scanner.resource_scanner_registry import ResourceScannerRegistry
from reports.html.report_generator import generate_html_report  # Import the function
from integrations.atlassian.confluence.report_uploader import ConfluenceReportUploader

# Configure logger
logger = logging.getLogger(__name__)

def load_scanners_and_parse_arguments():
    """Loads scanners and parses arguments."""
    args = ArgumentParser.parse_arguments()
    ResourceScannerRegistry.register_scanners_from_directory("scanner/aws/services")
    
    return args

def create_session_manager(args):
    """Initializes and returns the session manager."""
    return AWSSessionManager(
        profile_name=args.profile,
        organization_role=args.organization_role,
        runner_role=args.runner_role
    )

def main():
    try:
        # Load arguments and scanners
        args = load_scanners_and_parse_arguments()
        logger.debug(f"Parsed arguments: {args}")
        scanners = ArgumentParser.get_scanners(args)

        # Initialize session manager
        session_manager = create_session_manager(args)

        # Initialize and execute the scan
        executor = Executor(session=session_manager, scanners=scanners, regions=args.regions, max_workers=args.max_workers)
        scan_results, scan_metrics = executor.execute()

        # Generate and save the report
        report_filename = generate_html_report(
            scan_results=scan_results,
            start_time=scan_metrics["start_time"],
            scan_metrics=scan_metrics
        )

        logger.info(f"HTML report generated successfully: {report_filename}")

    except Exception as e:
        logger.exception(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
