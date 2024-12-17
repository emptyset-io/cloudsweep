import os
from datetime import datetime
import pytz
from jinja2 import Environment, FileSystemLoader
from utils.logger import get_logger
from scanner.resource_scanner_registry import ResourceScannerRegistry

logger = get_logger(__name__)

def get_directories():
    """Retrieve template and asset directories."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    logger.debug(base_dir)
    template_dir = os.path.join(base_dir, "templates")
    logger.debug(template_dir)
    asset_dir = os.path.join(base_dir, "assets")

    if not os.path.exists(template_dir):
        raise FileNotFoundError(f"Template directory not found: {template_dir}")
    if not os.path.exists(asset_dir):
        raise FileNotFoundError(f"Asset directory not found: {asset_dir}")

    return template_dir, asset_dir

def load_asset(asset_path):
    """Load the content of a specified asset file."""
    try:
        logger.debug(f"Loading asset from {asset_path}")
        with open(asset_path, "r") as file:
            return file.read()
    except FileNotFoundError:
        logger.error(f"Asset not found: {asset_path}")
        return ""

def calculate_duration(total_scan_time):
    """Calculate the scan duration in a human-readable format."""
    duration = round(total_scan_time, 2)
    days, remainder = divmod(duration, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    if days > 0:
        duration_str = f"{int(days)} day(s) {int(hours)} hour(s)"
    elif hours > 0:
        duration_str = f"{int(hours)} hour(s) {int(minutes)} minute(s)"
    elif minutes > 0:
        duration_str = f"{int(minutes)} minute(s) {int(seconds)} second(s)"
    else:
        duration_str = f"{int(seconds)} second(s)"

    logger.debug(f"Calculated duration: {duration_str}")
    return duration, duration_str

def calculate_totals(combined_costs):
    """
    Compute totals for combined costs and add a 'Totals' row.
    """
    total_row = {
        "hourly": 0,
        "daily": 0,
        "monthly": 0,
        "yearly": 0,
        "lifetime": 0,
    }

    for costs in combined_costs.values():
        if costs:  # Ensure the costs dictionary is not None
            total_row["hourly"] += costs.get("hourly", 0)
            total_row["daily"] += costs.get("daily", 0)
            total_row["monthly"] += costs.get("monthly", 0)
            total_row["yearly"] += costs.get("yearly", 0)
            if not costs.get("lifetime", "N/A") == "N/A":
                total_row["lifetime"] += costs.get("lifetime", 0)

    combined_costs["Totals"] = total_row
    return combined_costs

def format_report_time(start_time):
    """Format the report start time in UTC."""
    utc_time = pytz.utc.localize(datetime.utcfromtimestamp(start_time))
    formatted_time = utc_time.strftime("%Y-%m-%d %H:%M:%S")
    logger.debug(f"Formatted report start time: {formatted_time}")
    return formatted_time

def parse_currency(currency_str):
    """Parse a currency string into a float."""
    return float(currency_str.replace('$', '').replace(',', '')) if currency_str else 0.0

def extract_scan_data(scan_results):
    """Extract and process scan data for report generation."""
    logger.info("Starting extraction of scan data...")
    accounts_and_regions = {}
    resource_type_counts = {}
    resources = []
    combined_costs = {}

    resource_scanner_registry = ResourceScannerRegistry
    logger.debug(f"Initialized ResourceScannerRegistry: {resource_scanner_registry}")

    for account_data in scan_results:
        logger.debug(f"Processing account data: {account_data}")
        account_id = account_data.get("account_id", "N/A")
        account_name = account_data.get("account_name", "Unknown Account")
        account_id_name = f"{account_id} - {account_name}"  # Combine account_id and account_name
        regions = [r for r in account_data.get("regions", []) if r != "Global"]
        logger.info(f"Account ID: {account_id_name}, Regions: {regions}")
        scan_data = account_data.get("scan_results", {})

        if account_id_name not in accounts_and_regions:
            accounts_and_regions[account_id_name] = []
        accounts_and_regions[account_id_name].extend([r for r in regions if r not in accounts_and_regions[account_id_name]])
        logger.debug(f"Updated accounts and regions: {accounts_and_regions}")

        for region, region_data in scan_data.items():
            logger.debug(f"Processing region: {region}, data: {region_data}")
            for resource_type, resource_list in region_data.items():
                try:
                    logger.debug(f"Processing resource type: {resource_type}, resources: {resource_list}")
                    scanner = resource_scanner_registry.get_scanner(resource_type)
                    label = scanner.label
                    logger.debug(f"Found scanner for resource type '{resource_type}' with label '{label}'")
                    resource_type_counts[label] = resource_type_counts.get(label, 0) + len(resource_list)

                    for resource in resource_list:
                        resource_details = format_resource_details(resource).replace("\n", "<br/><br/>")
                        logger.debug(f"Processed resource details: {resource_details}")

                        resources.append({
                            "account_id_name": account_id_name,  # Use account_id_name here
                            "region": region,
                            "resource_type": label,
                            "name": resource.get("ResourceName", "N/A"),
                            "resource_id": resource.get("ResourceId", "N/A"),
                            "reason": resource.get("Reason", "N/A"),
                            "details": resource_details
                        })
                        if resource.get("Cost", {}):
                            cost_data = resource.get("Cost", {}).get(label, {})
                            for k, v in cost_data.items():
                                combined_costs.setdefault(label, {}).setdefault(k, 0)
                                if v != "N/A":
                                    combined_costs[label][k] += v
                                else:
                                    combined_costs[label][k] = v
                            logger.debug(f"Updated combined costs for {label}: {combined_costs[label]}")

                except ValueError:
                    logger.error(f"Scanner not found for resource type: {resource_type}")

    logger.info("Completed extraction of scan data.")
    logger.debug(f"Accounts and Regions: {accounts_and_regions}")
    logger.debug(f"Resource Type Counts: {resource_type_counts}")
    logger.debug(f"Resources: {resources}")
    logger.debug(f"Combined Costs: {combined_costs}")
    return accounts_and_regions, resource_type_counts, resources, combined_costs

def format_resource_details(resource):
    """Format resource details for display in the report."""
    if isinstance(resource, dict):
        return "\n".join([f"{k}: {v}" for k, v in resource.items()])
    elif isinstance(resource, list):
        return "\n".join(str(item) for item in resource)
    return str(resource)

def render_html(template_dir, template_path, context):
    """Render an HTML template with the given context."""
    logger.debug(f"Rendering template: {template_path}")
    env = Environment(loader=FileSystemLoader(searchpath=template_dir))
    template = env.get_template(template_path)
    return template.render(context)

def save_html(content, filename):
    """Save the generated HTML content to a file."""
    logger.debug(f"Saving HTML content to file: {filename}")
    with open(filename, 'w') as file:
        file.write(content)

def generate_html_report(scan_results, start_time, scan_metrics, filename="scan_report.html"):
    """Main function to generate an HTML report."""
    logger.info("Generating HTML report")
    template_dir, asset_dir  = get_directories()
    accounts_and_regions, resource_type_counts, resources, totals = extract_scan_data(scan_results)
    _, duration_str = calculate_duration(scan_metrics.get("total_run_time", 0))
    scan_metrics["total_run_time"] = duration_str

    report_generated_at = format_report_time(start_time)
    styles = load_asset(os.path.join(asset_dir, 'styles.css'))
    scripts = load_asset(os.path.join(asset_dir, 'scripts.js'))
    combined_costs = calculate_totals(totals)
    logger.critical(accounts_and_regions)
    context = {
        "accounts_and_regions": accounts_and_regions,
        "report_generated_at": report_generated_at,
        "resource_type_counts": resource_type_counts,
        "resources": resources,
        "start_time": start_time,
        "styles": styles,
        "scripts": scripts,
        "scan_metrics": scan_metrics,
        "combined_costs": combined_costs,
    }

    html_content = render_html(template_dir, "scan_report_template.j2", context)
    save_html(html_content, filename)
    logger.info(f"Report generated successfully: {filename}")
    return filename
