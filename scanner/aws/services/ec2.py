from datetime import datetime, timedelta, timezone
from dateutil import parser
from utils.logger import get_logger
from config.config import DAYS_THRESHOLD
from scanner.resource_scanner_registry import ResourceScannerRegistry

logger = get_logger(__name__)

class Ec2Scanner(ResourceScannerRegistry):
    """
    Scanner for EC2 Instances.
    """
    argument_name = "ec2"
    label = "EC2 Instances"

    def __init__(self):
        super().__init__(name=__name__, argument_name=self.argument_name, label=self.label)

    def scan(self, session, *args, **kwargs):
        """Retrieve EC2 instances and flag them if they are underutilized or unused."""
        logger.debug("Retrieving EC2 instances...")
        try:
            instances = session.get_client("ec2").describe_instances()["Reservations"]
            unused_instances = []
            current_time = datetime.now(timezone.utc)

            for reservation in instances:
                for instance in reservation["Instances"]:
                    instance_id = instance["InstanceId"]
                    instance_state = instance["State"]["Name"]

                    logger.debug(f"Processing EC2 instance {instance_id} with state {instance_state}...")

                    # Retrieve instance name
                    instance_name = "Unnamed"
                    if "Tags" in instance:
                        for tag in instance["Tags"]:
                            if tag["Key"] == "Name":
                                instance_name = tag["Value"]
                                break

                    # Check if the instance is stopped
                    if instance_state == "stopped":
                        state_transition_reason = instance.get("StateTransitionReason", "")
                        stopped_duration = self._parse_state_transition_reason(state_transition_reason, current_time)

                        # Fallback if parsing fails
                        if stopped_duration is None:
                            stopped_duration = DAYS_THRESHOLD + 1

                        if stopped_duration >= DAYS_THRESHOLD:
                            unused_instances.append({
                                "InstanceId": instance_id,
                                "Name": instance_name,
                                "State": instance_state,
                                "Reason": f"Stopped for {stopped_duration} days",
                                "AccountId": session.account_id,
                            })
                            logger.info(f"EC2 instance {instance_id} ({instance_name}) is unused: Stopped for {stopped_duration} days")
                        continue

                    # Analyze running instances for underutilization
                    if instance_state == "running":
                        launch_time = instance["LaunchTime"]
                        days_since_launch = (current_time - launch_time).days
                        start_time = launch_time if days_since_launch < DAYS_THRESHOLD else current_time - timedelta(days=DAYS_THRESHOLD)

                        # Fetch metrics
                        instance_usage = self._check_instance_usage(session.get_client("cloudwatch"), instance_id, start_time, current_time)
                        reasons = []

                        if instance_usage["cpu"] < 1:  # Low CPU usage threshold
                            reasons.append(f"Low CPU utilization ({instance_usage['cpu']:.2f}%)")
                        if instance_usage["network"] < 1:  # No network traffic
                            reasons.append("Low network traffic")

                        if reasons:
                            unused_instances.append({
                                "InstanceId": instance_id,
                                "Name": instance_name,
                                "State": instance_state,
                                "LaunchTime": launch_time,
                                "AccountId": session.account_id,
                                "Reason": ", ".join(reasons),
                            })
                            logger.info(f"EC2 instance {instance_id} ({instance_name}) is underutilized: {', '.join(reasons)}")

            logger.info(f"Found {len(unused_instances)} unused or underutilized EC2 instances.")
            return unused_instances
        except Exception as e:
            logger.error(f"Error retrieving EC2 instances: {e}")
            return []

    def _parse_state_transition_reason(self, state_transition_reason, current_time):
        """
        Parse the StateTransitionReason string and calculate the stopped duration.

        :param state_transition_reason: The reason string from the EC2 instance.
        :param current_time: The current timezone-aware datetime object.
        :return: The duration in days the instance has been stopped, or None if parsing fails.
        """
        if not state_transition_reason or "(" not in state_transition_reason or ")" not in state_transition_reason:
            return None

        try:
            # Extract the timestamp from the reason string
            timestamp_str = state_transition_reason.split("(")[-1].strip(")")

            # Use dateutil.parser to parse the timestamp string
            stopped_time = parser.parse(timestamp_str)

            # Ensure the parsed time is in UTC timezone
            stopped_time = stopped_time.astimezone(timezone.utc)

            # Return the difference in days
            return (current_time - stopped_time).days
        except Exception as e:
            logger.warning(f"Could not parse timestamp from {state_transition_reason}: {e}")
            return None

    def _check_instance_usage(self, cloudwatch_client, instance_id, start_time, end_time):
        """
        Check the EC2 instance's usage metrics: CPU, network, and disk I/O.

        :param cloudwatch_client: Boto3 CloudWatch client
        :param instance_id: EC2 instance ID
        :param start_time: Start time for metric retrieval
        :param end_time: End time for metric retrieval
        :return: Dictionary containing CPU, network traffic, and disk I/O metrics
        """
        logger.debug(f"Fetching metrics for EC2 instance {instance_id} from {start_time} to {end_time}...")

        metrics = {
            "cpu": 0,
            "network": 0,
            "disk_read": 0,
            "disk_write": 0,
        }

        try:
            # CPU Utilization
            cpu_data = cloudwatch_client.get_metric_data(
                MetricDataQueries=[{
                    'Id': 'cpuUsage',
                    'MetricStat': {
                        'Metric': {
                            'Namespace': 'AWS/EC2',
                            'MetricName': 'CPUUtilization',
                            'Dimensions': [{'Name': 'InstanceId', 'Value': instance_id}]
                        },
                        'Period': 3600,
                        'Stat': 'Average'
                    },
                    'ReturnData': True
                }],
                StartTime=start_time,
                EndTime=end_time
            )['MetricDataResults'][0]['Values']

            metrics["cpu"] = sum(cpu_data) / len(cpu_data) if cpu_data else 0

            # Network Traffic
            network_data = cloudwatch_client.get_metric_data(
                MetricDataQueries=[{
                    'Id': 'networkTraffic',
                    'MetricStat': {
                        'Metric': {
                            'Namespace': 'AWS/EC2',
                            'MetricName': 'NetworkPacketsIn',
                            'Dimensions': [{'Name': 'InstanceId', 'Value': instance_id}]
                        },
                        'Period': 3600,
                        'Stat': 'Sum'
                    },
                    'ReturnData': True
                }],
                StartTime=start_time,
                EndTime=end_time
            )['MetricDataResults'][0]['Values']

            metrics["network"] = sum(network_data) if network_data else 0

        except Exception as e:
            logger.error(f"Error fetching metrics for instance {instance_id}: {e}")

        return metrics
