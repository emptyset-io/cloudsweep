#!/usr/bin/env python
import logging
import os
from dotenv import load_dotenv
from scanner.executor import Executor
from scanner.aws.session_manager import AWSSessionManager
from scanner.argument_parser import ArgumentParser
from scanner.resource_scanner_registry import ResourceScannerRegistry
from integrations.atlassian.confluence.report_uploader import ConfluenceReportUploader
from reports.html.report_generator import generate_html_report

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def setup_scanners():
    """Registers all resource scanners."""
    ResourceScannerRegistry.register_scanners_from_directory("scanner/aws/services")

def parse_and_prepare_args():
    """Parses CLI arguments and prepares necessary objects."""
    args = ArgumentParser.parse_arguments()
    logger.debug(f"Parsed arguments: {args}")
    scanners = ArgumentParser.get_scanners(args)
    regions = ArgumentParser.get_regions(args)

    session_manager = AWSSessionManager(
        organization_role=args.organization_role,
        runner_role=args.runner_role,
    )
    accounts = ArgumentParser.get_accounts(args, session_manager=session_manager)
    return args, scanners, regions, session_manager, accounts

def is_scan_results_empty(scan_results):
    """Checks if scan results are empty across all accounts, regions, and services."""
    for account in scan_results:
        for region, services in account['scan_results'].items():
            for service, results in services.items():
                if results:
                    return False
    return True

def generate_report(scan_results, scan_metrics):
    """Generates the report if scan results are non-empty."""
    if is_scan_results_empty(scan_results):
        logger.info("No results found, skipping report generation.")
        return None

    report_filename = generate_html_report(
        scan_results=scan_results,
        start_time=scan_metrics["start_time"],
        scan_metrics=scan_metrics
    )
    logger.debug(f"Report successfully generated: {report_filename}")
    return report_filename

def extract_account_details_from_scan_results(scan_results):
    """Extracts account_id and account_name from the scan results."""
    account_details = {}

    # Loop over the scan results to extract account_id and account_name
    for account in scan_results:
        account_id = account.get('account_id')
        account_name = account.get('account_name')
        
        if account_id and account_name:
            # Add account_id and account_name to the dictionary
            account_details[account_id] = account_name
    
    logger.critical(account_details)
    return account_details

def upload_report_to_confluence(report_filename, account_details):
    """Uploads the generated report to Confluence."""
    if report_filename:
        confluence_url = os.getenv("CS_ATLASSIAN_BASE_URL")
        username = os.getenv("CS_ATLASSIAN_USERNAME")
        api_token = os.getenv("CS_ATLASSIAN_API_TOKEN")
        parent_page_title = int(os.getenv("CS_CONFLUENCE_PARENT_PAGE"))
        space_key = os.getenv("CS_CONFLUENCE_SPACE_KEY")

        for account_id, account_name in account_details.items():
            confluence_uploader = ConfluenceReportUploader(
                confluence_url=confluence_url,
                username=username,
                api_token=api_token,
                parent_page_title=parent_page_title
            )
            confluence_uploader.upload_report(
                space_key=space_key,
                page_title=f"{account_name}",
                report_file_path=report_filename,
                account_id=account_id
            )


def handle_confluence_upload(args, report_filename, account_details):
    """Handles uploading the report to Confluence based on the provided argument."""
    if args.upload_confluence:
        logger.info("Uploading report to Confluence...")
        upload_report_to_confluence(report_filename, account_details)
        logger.info("Report uploaded successfully!")
    else:
        logger.info("Confluence upload skipped.")

def main():
    """Main entry point of the script."""
    try:
        setup_scanners()
        args, scanners, regions, session_manager, accounts = parse_and_prepare_args()

        executor = Executor(
            session=session_manager,
            accounts=accounts,
            scanners=scanners,
            regions=regions,
            max_workers=args.max_workers
        )

        scan_results, scan_metrics = executor.execute()

        # Generate the report
        report_filename = generate_report(scan_results, scan_metrics)

        if report_filename:
            account_details = extract_account_details_from_scan_results(scan_results)
            handle_confluence_upload(args, report_filename, account_details)

    except Exception as e:
        logger.exception(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
