from datetime import datetime, timedelta, timezone
from utils.logger import get_logger
from config.config import DAYS_THRESHOLD
from scanner.resource_scanner_registry import ResourceScannerRegistry

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

                # Check the instance creation time
                creation_time = instance["InstanceCreateTime"]
                days_since_creation = (current_time - creation_time).days

                # Determine the start time for metrics
                start_time = max(creation_time, current_time - timedelta(days=DAYS_THRESHOLD))

                # Check RDS instance usage
                instance_usage = self._check_rds_usage(cloudwatch_client, instance_id, start_time, current_time)
                reason = None
                if instance_usage.get("connections") == 0:
                    reason = "No active connections."
                elif instance_usage.get("cpu_usage") < 1:  # Low CPU utilization threshold
                    reason = f"Low CPU utilization ({instance_usage['cpu_usage']}%)."
                elif instance_usage.get("read_iops") + instance_usage.get("write_iops") == 0:
                    reason = "No read/write I/O activity."

                if reason:
                    unused_instances.append({
                        "DBInstanceIdentifier": instance_id,
                        "DBClusterIdentifier": cluster_id,
                        "DBInstanceClass": instance["DBInstanceClass"],
                        "Engine": instance["Engine"],
                        "InstanceCreateTime": creation_time,
                        "Connections": instance_usage["connections"],
                        "CPUUsage": instance_usage["cpu_usage"],
                        "ReadIOPS": instance_usage["read_iops"],
                        "WriteIOPS": instance_usage["write_iops"],
                        "AccountId": session.account_id,
                        "Reason": reason
                    })
                    logger.debug(f"RDS instance {instance_id} is unused or underutilized: {reason}")

            logger.info(f"Found {len(unused_instances)} unused RDS instances.")
            return unused_instances
        except Exception as e:
            logger.error(f"Error during RDS scan: {e}")
            return []

    @staticmethod
    def _check_rds_usage(cloudwatch_client, instance_id, start_time, end_time):
        """
        Check the RDS instance's CPU, connections, and I/O metrics.

        :param cloudwatch_client: Boto3 CloudWatch client.
        :param instance_id: The ID of the RDS instance to check.
        :param start_time: The start time for metrics.
        :param end_time: The end time for metrics.
        :return: Dictionary with CPU usage, connections, read IOPS, and write IOPS.
        """
        logger.debug(f"Checking usage for RDS instance {instance_id} from {start_time} to {end_time}...")
        try:
            metrics = {
                "cpu_usage": RDSScanner._get_metric_average(cloudwatch_client, instance_id, "CPUUtilization", start_time, end_time),
                "connections": RDSScanner._get_metric_maximum(cloudwatch_client, instance_id, "DatabaseConnections", start_time, end_time),
                "read_iops": RDSScanner._get_metric_sum(cloudwatch_client, instance_id, "ReadIOPS", start_time, end_time),
                "write_iops": RDSScanner._get_metric_sum(cloudwatch_client, instance_id, "WriteIOPS", start_time, end_time),
            }
            return metrics
        except Exception as e:
            logger.error(f"Error checking usage for RDS instance {instance_id}: {e}")
            return {"cpu_usage": 0, "connections": 0, "read_iops": 0, "write_iops": 0}

    @staticmethod
    def _get_metric_average(cloudwatch_client, instance_id, metric_name, start_time, end_time):
        return RDSScanner._get_metric_data(cloudwatch_client, instance_id, metric_name, "Average", start_time, end_time)

    @staticmethod
    def _get_metric_maximum(cloudwatch_client, instance_id, metric_name, start_time, end_time):
        return RDSScanner._get_metric_data(cloudwatch_client, instance_id, metric_name, "Maximum", start_time, end_time)

    @staticmethod
    def _get_metric_sum(cloudwatch_client, instance_id, metric_name, start_time, end_time):
        return RDSScanner._get_metric_data(cloudwatch_client, instance_id, metric_name, "Sum", start_time, end_time)

    @staticmethod
    def _get_metric_data(cloudwatch_client, instance_id, metric_name, stat, start_time, end_time):
        """
        Helper method to fetch metric data from CloudWatch.

        :param cloudwatch_client: Boto3 CloudWatch client.
        :param instance_id: The ID of the RDS instance.
        :param metric_name: Name of the CloudWatch metric.
        :param stat: Statistical method (e.g., 'Average', 'Sum', 'Maximum').
        :param start_time: Start time for fetching metrics.
        :param end_time: End time for fetching metrics.
        :return: Aggregated metric value or 0 if no data is found.
        """
        try:
            response = cloudwatch_client.get_metric_data(
                MetricDataQueries=[{
                    'Id': metric_name.lower(),
                    'MetricStat': {
                        'Metric': {
                            'Namespace': 'AWS/RDS',
                            'MetricName': metric_name,
                            'Dimensions': [{'Name': 'DBInstanceIdentifier', 'Value': instance_id}]
                        },
                        'Period': 3600,
                        'Stat': stat
                    },
                    'ReturnData': True
                }],
                StartTime=start_time,
                EndTime=end_time
            )
            values = response['MetricDataResults'][0].get('Values', [])
            if stat in ['Average', 'Sum']:
                return sum(values) / len(values) if values else 0
            elif stat == 'Maximum':
                return max(values) if values else 0
        except Exception as e:
            logger.error(f"Error fetching {metric_name} data for RDS instance {instance_id}: {e}")
            return 0
