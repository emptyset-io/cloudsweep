import random
import string
from datetime import datetime
from reports.html.report_generator import HTMLReportGenerator

# Updated Resource Type to Reason Mapping
RESOURCE_TYPE_REASONS = {
    "cloudformation": [
        "Resource is in terminal state (DELETE_COMPLETE).",
        "Stack is in terminal state (ROLLBACK_COMPLETE)."
    ],
    "dynamodb": [
        "No read or write activity."
    ],
    "ebs-volumes": [
        "Volume has been unattached for 100 days.",
        "Volume has been unattached for 113 days.",
        "Volume has been unattached for 114 days."
    ],
    "ec2": [
        "Low network traffic (0.12%)",
        "Low disk I/O activity (0.17%)",
        "Stopped for over a week"
        "Low CPU utilization (0.21%)."
    ],
    "rds": [
        "No active connections.",
        "Low network traffic (0.12%)",
        "Low disk I/O activity (0.17%)",
        "Stopped for over a week"
        "Low CPU utilization (0.21%)."
    ],
    "s3": [
        "No objects in bucket.",
        "No change in object count over the 90-day threshold period."
    ],
    "iam-roles": [
        "Role has never been used.",
        "Role has not been used in the last 90 days (107 days ago).",
    ],
    "iam-users": [
        "UI login last used 126 days ago. Access keys last used 630 days ago.",
        "UI login last used 150 days ago. Access keys last used 150 days ago.",
        "UI login last used 155 days ago. Access keys last used 155 days ago.",
        "UI login last used 192 days ago. Access keys last used 1323 days ago.",
        "UI login last used 1925 days ago. Access keys last used 90 days ago.",
        "UI login last used 215 days ago. Access keys last used 667 days ago.",
        "UI login last used 225 days ago. Access keys last used 494 days ago.",
        "UI login last used 2663 days ago. Access keys last used 1163 days ago.",
        "UI login last used 275 days ago. Access keys last used 289 days ago.",
        "UI login last used 311 days ago. Access keys last used 414 days ago."
    ],
    "elastic-ips": [
        "Not associated with any resource (EC2 Instance)."
    ],
    "load-balancers": [
        "No traffic recorded during the threshold period of 90 days."
    ],
    "vpcs": [
        "No Resources, VPC is empty."
    ]
}


# Random string generator
def random_string(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# Function to generate a random AWS-style account ID (12 digits)
def random_account_id():
    return str(random.randint(100000000000, 999999999999))

# Function to generate a random account
def generate_random_account(account_id, regions, resource_types):
    account_data = {}
    total_resources = 0  # Initialize total resources counter for this account
    selected_regions = random.sample(regions, random.randint(1, len(regions)))  # Select a random subset of regions for this account

    for region in selected_regions:
        region_data = {}
        for resource_type in resource_types:
            # Random number of resources between 1 and 3 per resource type
            resources = []
            for _ in range(random.randint(1, 3)):
                resource_name = f"{resource_type.capitalize()}-{random_string()}"
                resource_id = f"res-{random_string(8)}"
                reason = random.choice(RESOURCE_TYPE_REASONS.get(resource_type, []))
                resources.append({
                    "ResourceName": resource_name,
                    "ResourceId": resource_id,
                    "Reason": reason
                })
            region_data[resource_type] = resources
            total_resources += len(resources)  # Update total resources for this account
        account_data[region] = region_data

    return account_data, selected_regions, total_resources  # Return account data, selected regions, and total resources

# Function to generate randomized report data for 5 dummy accounts
def generate_random_report_data(num_accounts=5):
    accounts = [random_account_id() for _ in range(num_accounts)]  # Generate 12-digit AWS account IDs
    regions = [
        "us-east-1", "us-east-2","us-west-1", "us-west-2", "eu-west-1", "eu-central-1", 
        "ap-southeast-1", "ap-southeast-2", "ap-northeast-1", "sa-east-1", 
        "ca-central-1", "eu-west-2", "af-south-1",
    ]
    resource_types = list(RESOURCE_TYPE_REASONS.keys())

    report_data = []
    total_scans = 0  # Initialize the total scans counter

    for account in accounts:
        account_data, selected_regions, total_resources = generate_random_account(account, regions, resource_types)
        total_scans += total_resources  # Add the resources for this account to the total scans

        # Include the selected regions in the scan results
        report_data.append({
            "account_id": account,
            "scan_results": account_data,
            "regions": selected_regions  # Add the list of selected regions directly in the scan results
        })
    
    return report_data, total_scans  # Return both report data and total scans

# Example usage:
random_report_data, total_scans = generate_random_report_data()

# Initialize the report generator
report_generator = HTMLReportGenerator()
# Assuming ResourceScannerRegistry is set up as before
from scanner.resource_scanner_registry import ResourceScannerRegistry
ResourceScannerRegistry.register_scanners_from_directory("scanner/aws/services")

# Example metrics for the scan
scan_metrics = {
    "total_run_time": 120.5,  # Example: 120.5 seconds of scanning
    "total_scans": total_scans,  # Add the total scans metric
    "avg_scans_per_second": f"{(total_scans / 120.5):.2f}"
}

# Generate the report
start_time = datetime.utcnow().timestamp()  # Use current UTC time
html_report = report_generator.generate_html(random_report_data, start_time, scan_metrics, filename="random_scan_report.html")

# Output the total number of scans for this run
print(f"Total scans: {total_scans}")