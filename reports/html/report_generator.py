import os
import time
from datetime import datetime
import pytz
from jinja2 import Environment, FileSystemLoader
from utils.logger import get_logger
from scanner.resource_scanner_registry import ResourceScannerRegistry

logger = get_logger(__name__)
        


class HTMLReportGenerator:
    """
    Class to generate HTML reports from AWS scan results.

    This class is responsible for processing scan data, formatting the report, 
    rendering it using Jinja2 templates, and saving it as an HTML file.
    """
    def __init__(self):
        """
        Initializes the report generator with template and asset directories.
        The template and asset directories are set relative to the current file's directory.
        """
        # Get the absolute path of the current file
        base_dir = os.path.dirname(os.path.abspath(__file__))

        # Set the directories relative to the current script location
        self.template_dir = os.path.join(base_dir, "templates")
        self.asset_dir = os.path.join(base_dir, "assets")
        self.resource_scanner_registry = ResourceScannerRegistry
        # Ensure the directories exist (optional, for validation)
        if not os.path.exists(self.template_dir):
            raise FileNotFoundError(f"Template directory not found: {self.template_dir}")
        if not os.path.exists(self.asset_dir):
            raise FileNotFoundError(f"Asset directory not found: {self.asset_dir}")
    
    def _load_asset(self, asset_path):
        """
        Utility function to load file content from the given path.
        
        :param asset_path: Path to the asset file (CSS, JS, etc.).
        :return: File content as a string.
        """
        try:
            logger.debug(f"Loading asset from {asset_path}")
            with open(asset_path, "r") as file:
                return file.read()
        except FileNotFoundError:
            logger.error(f"Asset not found: {asset_path}")
            return ""
    
    def _calculate_duration(self, total_scan_time):
        """
        Calculate the duration from the total scan time (in seconds) and return it
        in a human-readable format based on whether it is seconds, minutes, hours, or days.

        :param total_scan_time: The total scan time in seconds (floating-point number).
        :return: Duration in seconds and human-readable format.
        """
        duration = round(total_scan_time, 2)

        # Calculate the time breakdown
        days, remainder = divmod(duration, 86400)  # 1 day = 86400 seconds
        hours, remainder = divmod(remainder, 3600)  # 1 hour = 3600 seconds
        minutes, seconds = divmod(remainder, 60)   # 1 minute = 60 seconds

        # Build the human-readable string dynamically
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

    
    def _format_report_time(self, start_time):
        """
        Format the report generation start time in UTC.
        
        :param start_time: The start time as a Unix timestamp.
        :return: The formatted start time in UTC.
        """
        utc_time = pytz.utc.localize(datetime.utcfromtimestamp(start_time))
        formatted_time = utc_time.strftime("%Y-%m-%d %H:%M:%S")
        logger.debug(f"Formatted report start time: {formatted_time}")
        return formatted_time
    
    def _extract_scan_data(self, scan_results):
        """
        Extract relevant data from scan results to be used in the report.

        :param scan_results: The scan results list containing resources and metadata.
        :return: A tuple containing accounts and regions, resource counts, and resource details.
        """
        logger.debug("Extracting scan data")
        accounts_and_regions = {}
        resource_type_counts = {}
        resources = []

        # Iterate through the scan results list
        for account_data in scan_results:
            account_id = account_data.get("account_id", "N/A")
            regions = account_data.get("regions", [])
            scan_data = account_data.get("scan_results", {})

            # Populate accounts and regions
            if account_id not in accounts_and_regions:
                accounts_and_regions[account_id] = []

            # Filter out the "Global" region
            filtered_regions = [region for region in regions if region != "Global"]

            # Only add regions that are not "Global"
            for region in filtered_regions:
                if region not in accounts_and_regions[account_id]:
                    accounts_and_regions[account_id].append(region)

            # Process each region's resources
            for region, region_data in scan_data.items():
                for resource_type, resource_list in region_data.items():
                    # Lookup the scanner using ResourceScannerMap
                    try:
                        scanner = self.resource_scanner_registry.get_scanner(resource_type)
                        label = scanner.label  # Get the name from the scanner
                        # Update resource type counts
                        resource_type_counts[label] = (
                            resource_type_counts.get(label, 0) + len(resource_list)
                        )

                        # Collect resource details
                        for resource in resource_list:
                            resources.append({
                                "account_id": account_id,
                                "region": region,
                                "resource_type": label,
                                "name": resource.get("ResourceName") or "N/A",
                                "resource_id": resource.get("ResourceId") or "N/A",
                                "reason": resource.get("Reason", "N/A"),
                                "details": self._format_resource_details(resource).replace("\n", "<br>")
                            })
                    except ValueError:
                        logger.error(f"Scanner not found for resource type: {resource_type}")

        return accounts_and_regions, resource_type_counts, resources

    
    def _render_html_template(self, template_path, context):
        """
        Render the Jinja2 template with the provided context.
        
        :param template_path: Path to the Jinja2 template.
        :param context: Data to be passed into the template for rendering.
        :return: Rendered HTML content.
        """
        logger.debug(f"Rendering template: {template_path}")
        env = Environment(loader=FileSystemLoader(searchpath=self.template_dir))
        template = env.get_template(template_path)
        return template.render(context)
    
    def _save_html_to_file(self, content, filename):
        """
        Save the generated HTML content to a file.
        
        :param content: The HTML content to be saved.
        :param filename: The output filename.
        """
        logger.debug(f"Saving HTML content to file: {filename}")
        with open(filename, 'w') as file:
            file.write(content)
    
    def generate_html(self, scan_results, start_time, scan_metrics, filename="scan_report.html"):
        """
        Generate an HTML report from scan results using Jinja2 templates.
        
        :param scan_results: The scan results containing resources and metadata.
        :param start_time: The start time of the scan (Unix timestamp).
        :param scan_metrics: Timings for the scan process.
        :param filename: The name of the output HTML file (default: "scan_report.html").
        :return: The generated HTML content.
        """
        logger.info("Generating HTML report")
        
        # Extract scan data
        accounts_and_regions, resource_type_counts, resources = self._extract_scan_data(scan_results)

        # Use the total_run_time from scan_metrics to calculate the duration
        total_scan_time = scan_metrics.get("total_run_time", 0)  # Ensure total_run_time is available in scan_metrics
        _, duration_str = self._calculate_duration(total_scan_time)

        # Overwrite scan_metrics.total_run_time with the human-readable duration
        scan_metrics["total_run_time"] = duration_str

        # Format report generation time
        report_generated_at = self._format_report_time(start_time)

        # Load external assets (CSS/JS)
        styles = self._load_asset(os.path.join(self.asset_dir, 'styles.css'))
        scripts = self._load_asset(os.path.join(self.asset_dir, 'scripts.js'))

        logger.debug(f"ScanTimings: {','.join(str(value) for value in scan_metrics)}")
        
        # Prepare context for template rendering
        context = {
            "accounts_and_regions": accounts_and_regions,
            "report_generated_at": report_generated_at,
            "resource_type_counts": resource_type_counts,
            "resources": resources,
            "start_time": start_time,
            "styles": styles,
            "scripts": scripts,
            "scan_metrics": scan_metrics,  # Now includes the updated total_run_time
        }

        # Render the HTML report
        html_content = self._render_html_template('./scan_report_template.j2', context)

        # Save the report to a file
        self._save_html_to_file(html_content, filename)

        logger.info(f"Report generated successfully: {filename}")
        return html_content

    def _format_resource_details(self, resource):
        """
        Format the resource details to make it suitable for CSV output.
        Converts dictionaries and lists to a formatted string where each key-value pair
        is printed on a new line. Handles nested structures (dictionaries, lists) properly.
        """
        def format_dict(data, indent_level=1):
            """Helper function to format dictionary details."""
            formatted = ""
            for key, value in data.items():
                formatted += f"{'  ' * indent_level}{key}: {value}\n"
            return formatted

        def format_list(data, indent_level=1):
            """Helper function to format list details."""
            formatted = ""
            for item in data:
                if isinstance(item, dict):
                    formatted += format_dict(item, indent_level)
                else:
                    formatted += f"{'  ' * indent_level}{item}\n"
            return formatted

        if isinstance(resource, dict):
            details = ""
            for key, value in resource.items():
                if isinstance(value, dict):
                    details += f"{key}:\n{format_dict(value)}"
                elif isinstance(value, list):
                    details += f"{key}:\n{format_list(value)}"
                else:
                    details += f"{key}: {value}\n"
            return details
        elif isinstance(resource, list):
            return format_list(resource, indent_level=0)
        else:
            return str(resource)