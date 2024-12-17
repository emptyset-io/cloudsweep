from datetime import datetime, timedelta, timezone
from utils.logger import get_logger
from config.config import DAYS_THRESHOLD
from scanner.resource_scanner_registry import ResourceScannerRegistry
from scanner.aws.utils.scanner_helper import fetch_metric, determine_metric_time_window, extract_tag_value

logger = get_logger(__name__)

class ElbScanner(ResourceScannerRegistry):
    """
    Scanner for Elastic Load Balancers (ELBs).
    """
    argument_name = "load-balancers"
    label = "Elastic Load Balancers"

    def __init__(self):
        super().__init__(name=__name__, argument_name=self.argument_name, label=self.label)

    def scan(self, session, *args, **kwargs):
        """Retrieve unused Load Balancers based on traffic metrics."""
        logger.debug("Retrieving unused Load Balancers based on traffic metrics...")
        try:
            elbv2_client = session.get_client("elbv2")
            cloudwatch_client = session.get_client("cloudwatch")
            load_balancers = elbv2_client.describe_load_balancers()["LoadBalancers"]
            unused_lb = []

            for lb in load_balancers:
                lb_arn = lb["LoadBalancerArn"]
                lb_name = self._get_load_balancer_name(elbv2_client, lb)

                logger.debug(f"Scanning Load Balancer {lb_name} ({lb_arn})...")
                
                # Retrieve CloudWatch metrics using the helper function
                metric_data = self._get_load_balancer_metrics(cloudwatch_client, lb_arn)

                # Check if Load Balancer is unused
                if self._is_unused_load_balancer(metric_data):
                    reason = self._determine_reason(metric_data)
                    unused_lb.append({
                        "ResourceName": lb_name,
                        "ResourceId": lb_arn,
                        "TrafficMetrics": metric_data,
                        "Name": lb_name,
                        "Reason": reason
                    })
                    logger.debug(f"Load Balancer {lb_name} is unused. Reason: {reason}")

            logger.info(f"Found {len(unused_lb)} unused Load Balancers.")
            return unused_lb

        except Exception as e:
            logger.error(f"Error retrieving Load Balancers: {e}")
            return []

    def _get_load_balancer_name(self, elbv2_client, lb):
        """Retrieve the Load Balancer name from attributes or tags."""
        lb_name = lb.get("LoadBalancerName", "Unnamed")
        if lb_name == "Unnamed":
            try:
                tags = elbv2_client.describe_tags(ResourceArns=[lb["LoadBalancerArn"]])["TagDescriptions"]
                for tag_description in tags:
                    for tag in tag_description.get("Tags", []):  # Safe access to the "Tags" list
                        if "Key" in tag and tag["Key"] == "Name":  # Ensure "Key" exists in the tag
                            return tag.get("Value", "Unnamed")  # Return tag value if present, else default to "Unnamed"
            except Exception as e:
                logger.warning(f"Could not retrieve tags for Load Balancer {lb['LoadBalancerArn']}: {e}")
        return lb_name


    def _get_load_balancer_metrics(self, cloudwatch_client, lb_arn):
        """Retrieve CloudWatch metrics for the Load Balancer."""
        try:
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(days=DAYS_THRESHOLD)

            total_requests = fetch_metric(cloudwatch_client, 'AWS/ApplicationELB', lb_arn, 'LoadBalancer', 'RequestCount', 'Sum', start_time, end_time)
            total_bytes_sent = fetch_metric(cloudwatch_client, 'AWS/ApplicationELB', lb_arn, 'LoadBalancer', 'ProcessedBytes', 'Sum', start_time, end_time)

            return {
                "TotalRequests": total_requests,
                "TotalBytesSent": total_bytes_sent,
                "RequestDeviation": self._calculate_request_deviation([total_requests])
            }

        except Exception as e:
            logger.error(f"Error retrieving metrics for Load Balancer {lb_arn}: {e}")
            return {"TotalRequests": 0, "TotalBytesSent": 0, "RequestDeviation": 0}

    def _calculate_request_deviation(self, request_count_data):
        """Calculate traffic variation based on the standard deviation."""
        if len(request_count_data) < 2:
            return 0
        mean = sum(request_count_data) / len(request_count_data)
        variance = sum((x - mean) ** 2 for x in request_count_data) / len(request_count_data)
        deviation = variance ** 0.5
        logger.debug(f"Calculated traffic deviation: {deviation}")
        return deviation

    def _is_unused_load_balancer(self, metric_data):
        """Determine if the Load Balancer is unused based on metrics."""
        if metric_data["TotalRequests"] == 0 and metric_data["TotalBytesSent"] == 0:
            return True
        if metric_data["RequestDeviation"] < 0.1:  # Low traffic variation
            return True
        return False

    def _determine_reason(self, metric_data):
        """Determine the reason for marking the Load Balancer as unused."""
        if metric_data["TotalRequests"] == 0 and metric_data["TotalBytesSent"] == 0:
            return f"No traffic recorded during the threshold period of {DAYS_THRESHOLD} days."
        if metric_data["RequestDeviation"] < 0.1:
            return "Low traffic variation (low deviation)."
        return "Unknown reason."
