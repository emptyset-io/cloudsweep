from datetime import datetime, timezone
from utils.logger import get_logger
from config.config import DAYS_THRESHOLD
from scanner.resource_scanner_registry import ResourceScannerRegistry
from scanner.aws.utils.scanner_helper import (
    determine_metric_time_window,
    fetch_metric,
    determine_unused_reason,
)
from scanner.aws.cost_estimator import CostEstimator

logger = get_logger(__name__)


class OpenSearchScanner(ResourceScannerRegistry):
    """
    Scanner for identifying unused Amazon OpenSearch clusters.
    """
    argument_name = "opensearch"
    label = "OpenSearch Clusters"

    def __init__(self):
        super().__init__(name=__name__, argument_name=self.argument_name, label=self.label)
        self.cost_estimator = CostEstimator()

    def scan(self, session, *args, **kwargs):
        """
        Retrieve and identify unused OpenSearch clusters and calculate costs.
        """
        logger.debug("Starting scan for unused OpenSearch clusters...")
        try:
            es_client = session.get_client("opensearch")
            cloudwatch_client = session.get_client("cloudwatch")
            domains = es_client.list_domain_names()["DomainNames"]
            unused_clusters = []
            current_time = datetime.now(timezone.utc)
            logger.debug(f"Found {len(domains)} Opensearch Clusters")
            for domain in domains:
                domain_name = domain["DomainName"]
                logger.debug(f"Checking OpenSearch cluster {domain_name} for usage...")

                # Fetch domain details
                domain_details = es_client.describe_domain(DomainName=domain_name)["DomainStatus"]
                creation_time = domain_details.get("Created", "Unknown")
                instance_type = domain_details.get("ClusterConfig", {}).get("InstanceType", "Unknown")
                instance_count = domain_details.get("ClusterConfig", {}).get("InstanceCount", 1)
                storage_type = domain_details.get("EBSOptions", {}).get("VolumeType", "Unknown")
                storage_size = domain_details.get("EBSOptions", {}).get("VolumeSize", 0)

                # Determine the metric time window
                start_time = determine_metric_time_window(creation_time, current_time, DAYS_THRESHOLD)

                # Fetch CloudWatch metrics for usage
                metrics = {
                    "cpu_utilization": fetch_metric(
                        cloudwatch_client, "AWS/ES", domain_name, "DomainName", "CPUUtilization", "Average", start_time, current_time
                    ),
                    "search_rate": fetch_metric(
                        cloudwatch_client, "AWS/ES", domain_name, "DomainName", "SearchRate", "Sum", start_time, current_time
                    ),
                    "index_rate": fetch_metric(
                        cloudwatch_client, "AWS/ES", domain_name, "DomainName", "IndexRate", "Sum", start_time, current_time
                    ),
                }

                # Calculate usage totals
                cpu_total = sum(metrics["cpu_utilization"])
                search_rate_total = sum(metrics["search_rate"])
                index_rate_total = sum(metrics["index_rate"])

                # Check for unused clusters
                unused_conditions = [
                    (lambda m: (search_rate_total == 0, "No search activity.")),
                    (lambda m: (index_rate_total == 0, "No indexing activity.")),
                    (lambda m: (cpu_total < 5, f"Low CPU utilization ({cpu_total}%)")),
                ]
                reason = determine_unused_reason(metrics, unused_conditions)

                # Calculate costs
                hours_running = (current_time - creation_time).total_seconds() / 3600
                instance_cost = self.cost_estimator.calculate_cost(
                    "EC2 Instances", resource_size=instance_type, hours_running=hours_running
                )
                ebs_cost = self.cost_estimator.calculate_cost(
                    "EBS Volumes", resource_size=storage_size, hours_running=hours_running
                )

                if reason:
                    unused_clusters.append({
                        "DomainName": domain_name,
                        "CreationTime": creation_time,
                        "InstanceType": instance_type,
                        "InstanceCount": instance_count,
                        "StorageType": storage_type,
                        "StorageSizeGB": storage_size,
                        "CPUUtilization": cpu_total,
                        "SearchRate": search_rate_total,
                        "IndexRate": index_rate_total,
                        "Reason": reason,
                        "Costs": {self.label: self._combined_costs([instance_cost,ebs_cost])
                        },
                    })
                    logger.debug(f"OpenSearch cluster {domain_name} is unused or underutilized: {reason}")

            logger.info(f"Found {len(unused_clusters)} unused OpenSearch clusters.")
            return unused_clusters
        except Exception as e:
            logger.error(f"Error during OpenSearch scan: {e}")
            return []

    def _combined_cost(self,costs_list):
        """
        Aggregates EC2 instance and EBS volume costs for hourly, daily, monthly, yearly, and lifetime.
        
        :param costs_list: A list of cost dictionaries, each containing cost categories ('hourly', 'daily', etc.).
        :return: A dictionary with aggregated costs for each category.
        """
        aggregated_costs = {
            "hourly": 0.0,
            "daily": 0.0,
            "monthly": 0.0,
            "yearly": 0.0,
            "lifetime": 0.0,
        }

        for cost in costs_list:
            for key in aggregated_costs:
                if key in cost and isinstance(cost[key], (int, float)):
                    aggregated_costs[key] += cost[key]

        return aggregated_costs