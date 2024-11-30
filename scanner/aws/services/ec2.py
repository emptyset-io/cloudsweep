from datetime import datetime, timedelta, timezone
from dateutil import parser
from utils.logger import get_logger
from config.config import DAYS_THRESHOLD
from scanner.resource_scanner_registry import ResourceScannerRegistry
from scanner.aws.utils.scanner_helper import extract_tag_value, fetch_metric

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
                    instance_name = extract_tag_value(instance.get("Tags"), key="Name")

                    # Check if the instance is stopped
                    if instance_state == "stopped":
                        stopped_duration = self._calculate_stopped_duration(
                            instance.get("StateTransitionReason"), current_time
                        )

                        if stopped_duration and stopped_duration >= DAYS_THRESHOLD:
                            unused_instances.append({
                                "ResourceId": instance_id,
                                "ResourceName": instance_name,
                                "State": instance_state,
                                "Reason": f"Stopped for {stopped_duration} days",
                                "AccountId": session.account_id,
                            })
                            logger.info(f"EC2 instance {instance_id} ({instance_name}) is unused: Stopped for {stopped_duration} days")
                        continue

                    # Analyze running instances for underutilization
                    if instance_state == "running":
                        reasons = self._analyze_instance_usage(session, instance, current_time)
                        if reasons:
                            unused_instances.append({
                                "ResourceId": instance_id,
                                "ResourceName": instance_name,
                                "State": instance_state,
                                "LaunchTime": instance["LaunchTime"],
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
            timestamp_str = state_transition_reason.split("(")[-1].strip(")")
            stopped_time = parser.parse(timestamp_str).astimezone(timezone.utc)
            return (current_time - stopped_time).days
        except Exception as e:
            logger.warning(f"Could not parse timestamp from {state_transition_reason}: {e}")
            return None
        
    def _calculate_stopped_duration(self, state_transition_reason, current_time):
        """Calculate the stopped duration based on the state transition reason."""
        return self._parse_state_transition_reason(state_transition_reason, current_time)

    def _analyze_instance_usage(self, session, instance, current_time):
        """Analyze EC2 instance usage for underutilization."""
        launch_time = instance["LaunchTime"]
        days_since_launch = (current_time - launch_time).days
        start_time = launch_time if days_since_launch < DAYS_THRESHOLD else current_time - timedelta(days=DAYS_THRESHOLD)

        instance_id = instance["InstanceId"]
        cloudwatch_client = session.get_client("cloudwatch")
        cpu_usage = fetch_metric(cloudwatch_client, "AWS/EC2", instance_id, "InstanceId", "CPUUtilization", "Average", start_time, current_time)
        network_usage = fetch_metric(cloudwatch_client, "AWS/EC2", instance_id, "InstanceId", "NetworkPacketsIn", "Sum", start_time, current_time)

        reasons = []
        if cpu_usage < 1:  # Low CPU usage threshold
            reasons.append(f"Low CPU utilization ({cpu_usage:.2f}%)")
        if network_usage < 1:  # No network traffic
            reasons.append("Low network traffic")

        return reasons
