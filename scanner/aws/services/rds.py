from datetime import datetime, timezone
from utils.logger import get_logger
from config.config import DAYS_THRESHOLD
from scanner.resource_scanner_registry import ResourceScannerRegistry
from scanner.aws.utils.scanner_helper import (
    determine_metric_time_window,
    fetch_metric,
    determine_unused_reason
)

logger = get_logger(__name__)

class RDSScanner(ResourceScannerRegistry):
    """
    Scanner for identifying unused RDS instances.
    """
    argument_name = "rds"
    label = "RDS Instances"

    def __init__(self):
        super().__init__(name=__name__, argument_name=self.argument_name, label=self.label)

    def scan(self, session, *args, **kwargs):
        """
        Retrieve and identify unused RDS instances based on key metrics like CPU, connections, and I/O.

        :param session: Boto3 session object for AWS API calls.
        :return: List of unused RDS instances with details.
        """
        logger.debug("Starting scan for unused RDS instances...")
        try:
            rds_client = session.get_client("rds")
            cloudwatch_client = session.get_client("cloudwatch")
            instances = rds_client.describe_db_instances().get("DBInstances", [])
            unused_instances = []
            current_time = datetime.now(timezone.utc)

            for instance in instances:
                instance_id = instance["DBInstanceIdentifier"]
                cluster_id = instance.get("DBClusterIdentifier", None)
                logger.debug(f"Checking RDS instance {instance_id} for usage...")

                creation_time = instance["InstanceCreateTime"]
                start_time = determine_metric_time_window(creation_time, current_time, DAYS_THRESHOLD)

                # Fetch CloudWatch metrics (note: the new fetch_metric returns a list of values)
                metrics = {
                    "cpu_usage": fetch_metric(cloudwatch_client, "AWS/RDS", instance_id, "DBInstanceIdentifier", "CPUUtilization", "Average", start_time, current_time),
                    "connections": fetch_metric(cloudwatch_client, "AWS/RDS", instance_id, "DBInstanceIdentifier", "DatabaseConnections", "Maximum", start_time, current_time),
                    "read_iops": fetch_metric(cloudwatch_client, "AWS/RDS", instance_id, "DBInstanceIdentifier", "ReadIOPS", "Sum", start_time, current_time),
                    "write_iops": fetch_metric(cloudwatch_client, "AWS/RDS", instance_id, "DBInstanceIdentifier", "WriteIOPS", "Sum", start_time, current_time)
                }

                # Sum the metric values to get totals for CPU, connections, and I/O
                cpu_usage_total = sum(metrics["cpu_usage"])  # Sum the CPU usage
                connections_total = sum(metrics["connections"])  # Sum the connections
                read_iops_total = sum(metrics["read_iops"])  # Sum the read IOPS
                write_iops_total = sum(metrics["write_iops"])  # Sum the write IOPS

                # Define unused conditions based on the summed metrics
                unused_conditions = [
                    (lambda m: (connections_total == 0, "No active connections.")),
                    (lambda m: (cpu_usage_total < 1, f"Low CPU utilization ({cpu_usage_total}%)")),
                    (lambda m: (read_iops_total + write_iops_total == 0, "No read/write I/O activity."))
                ]

                reason = determine_unused_reason(metrics, unused_conditions)
                if reason:
                    unused_instances.append({
                        "ResourceName": instance_id,
                        "ResourceId": cluster_id,
                        "DBInstanceClass": instance["DBInstanceClass"],
                        "Engine": instance["Engine"],
                        "InstanceCreateTime": creation_time,
                        "Connections": connections_total,
                        "CPUUsage": cpu_usage_total,
                        "ReadIOPS": read_iops_total,
                        "WriteIOPS": write_iops_total,
                        "Reason": reason
                    })
                    logger.debug(f"RDS instance {instance_id} is unused or underutilized: {reason}")

            logger.info(f"Found {len(unused_instances)} unused RDS instances.")
            return unused_instances
        except Exception as e:
            logger.error(f"Error during RDS scan: {e}")
            return []
