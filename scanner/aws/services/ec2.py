from datetime import datetime, timedelta, timezone
from dateutil import parser
from utils.logger import get_logger
from config.config import DAYS_THRESHOLD
from scanner.resource_scanner_registry import ResourceScannerRegistry
from scanner.aws.utils.scanner_helper import extract_tag_value, calculate_and_format_age_in_time_units
from scanner.aws.cost_estimator import CostEstimator
import numpy as np

logger = get_logger(__name__)

class Ec2Scanner(ResourceScannerRegistry):
    """
    Scanner for EC2 Instances.
    """
    argument_name = "ec2"
    label = "EC2 Instances"

    def __init__(self):
        super().__init__(name=__name__, argument_name=self.argument_name, label=self.label)
        self.cost_estimator = CostEstimator()  # Initialize Cost Estimator

    def scan(self, session, *args, **kwargs):
        """Retrieve EC2 instances and flag them if they are underutilized, unused, or in a non-running state."""
        logger.debug("Retrieving EC2 instances...")
        try:
            instances = session.get_client("ec2").describe_instances()["Reservations"]
            unused_instances = []
            current_time = datetime.now(timezone.utc)

            for reservation in instances:
                for instance in reservation["Instances"]:
                    instance_id = instance["InstanceId"]
                    instance_state = instance["State"]["Name"]
                    launch_time = instance["LaunchTime"]
                    hours_since_launch = self._calculate_running_hours(instance["LaunchTime"])
                    logger.debug(f"Processing EC2 instance {instance_id} with state {instance_state}...")
                    tags = instance.get("Tags")
                    # Retrieve instance name and class
                    instance_name = extract_tag_value(tags, key="Name")
                    instance_class = instance.get("InstanceType", "Unknown")

                    # Check if the instance is stopped
                    if instance_state == "stopped":
                        params = {
                            "state_transition_reason": instance.get("StateTransitionReason"),
                            "current_time": current_time
                        }
                        stopped_duration = self._calculate_stopped_duration(params)

                        if stopped_duration and stopped_duration >= DAYS_THRESHOLD:
                            # Use the calculate_and_format_age_in_time_units for stopped instances
                            age = calculate_and_format_age_in_time_units(current_time, launch_time)
                            reason = f"Stopped for {stopped_duration} days, greater than {DAYS_THRESHOLD} days. {age}"
                            ebs_details = self._get_ebs_volumes(session, instance)
                            hours_running = 0  # No running hours for stopped instances
                            cost_data = self._calculate_combined_costs(ebs_details=ebs_details, hours_running=hours_since_launch)
                            params = {
                                "instance": instance,
                                "instance_name": instance_name,
                                "instance_class": instance_class,
                                "tags": tags,
                                "reasons": [reason],
                                "session": session,
                                "stopped_duration": stopped_duration,
                                "ebs_details": ebs_details,
                                "cost_data": cost_data
                            }
                            unused_instances.append(self._build_unused_instance_response(params))
                            logger.info(f"EC2 instance {instance_id} ({instance_name}) is unused: {reason}")
                        continue

                    # Check for non-running instances
                    if instance_state != "running":
                        params = {
                            "instance": instance,
                            "current_time": current_time
                        }
                        state_change_duration = self._calculate_state_change_duration(params)

                        if state_change_duration and state_change_duration >= DAYS_THRESHOLD:
                            age = calculate_and_format_age_in_time_units(current_time, launch_time)
                            reason = f"Non-running state for {state_change_duration} days. {age}"
                            ebs_details = self._get_ebs_volumes(session, instance)
                            hours_running = 0  # No running hours for non-running instances
                            cost_data = self._calculate_combined_costs(ebs_details=ebs_details, hours_running=hours_since_launch)
                            params = {
                                "instance": instance,
                                "instance_name": instance_name,
                                "instance_class": instance_class,
                                "tags": tags,
                                "reasons": [reason],
                                "session": session,
                                "state_change_duration": state_change_duration,
                                "ebs_details": ebs_details,
                                "cost_data": cost_data
                            }
                            unused_instances.append(self._build_unused_instance_response(params))
                            logger.info(f"EC2 instance {instance_id} ({instance_name}) is in a non-running state: {instance_state} for {state_change_duration} days. {age}")
                        continue

                    # Check if instance has been running long enough before checking for underutilization
                    running_duration = (current_time - launch_time).days

                    if running_duration >= DAYS_THRESHOLD:
                        # Analyze running instances for underutilization
                        params = {
                            "session": session,
                            "instance": instance,
                            "current_time": current_time
                        }
                        reasons = self._analyze_instance_usage(params)
                        if reasons:  # Only log if there are reasons
                            hours_running = self._calculate_running_hours(launch_time)
                            ebs_details = self._get_ebs_volumes(session, instance)
                            cost_data = self._calculate_combined_costs(
                                ebs_details=ebs_details, instance_class=instance_class, hours_running=hours_since_launch
                            )
                            params = {
                                "instance": instance,
                                "tags": tags,
                                "instance_name": instance_name,
                                "instance_class": instance_class,
                                "reasons": reasons,
                                "session": session,
                                "hours_running": hours_running,
                                "ebs_details": ebs_details,
                                "cost_data": cost_data
                            }
                            unused_instances.append(self._build_unused_instance_response(params))
                            logger.info(f"EC2 instance {instance_id} ({instance_name}) is underutilized: {', '.join(reasons)}")
                    else:
                        logger.debug(f"EC2 instance {instance_id} ({instance_name}) has been running for {running_duration} days, skipping underutilization check.")

            logger.info(f"Found {len(unused_instances)} unused or underutilized EC2 instances.")
            return unused_instances
        except Exception as e:
            logger.exception(f"Error retrieving EC2 instances: {e}")
            return []

    def _calculate_state_change_duration(self, params):
        """Calculate the duration the instance has been in a non-running state (e.g., 'stopped', 'terminated')."""
        instance = params["instance"]
        current_time = params["current_time"]
        state_transition_reason = instance.get("StateTransitionReason")
        if not state_transition_reason or "(" not in state_transition_reason or ")" not in state_transition_reason:
            return None

        try:
            timestamp_str = state_transition_reason.split("(")[-1].strip(")")
            state_change_time = parser.parse(timestamp_str).astimezone(timezone.utc)
            return (current_time - state_change_time).days
        except Exception as e:
            logger.warning(f"Could not parse timestamp from {state_transition_reason}: {e}")
            return None

    def _calculate_stopped_duration(self, params):
        """Calculate the stopped duration based on the state transition reason."""
        state_transition_reason = params["state_transition_reason"]
        current_time = params["current_time"]
        return self._parse_state_transition_reason(state_transition_reason, current_time)

    def _parse_state_transition_reason(self, state_transition_reason, current_time):
        """Parse the StateTransitionReason string and calculate the stopped duration."""
        if not state_transition_reason or "(" not in state_transition_reason or ")" not in state_transition_reason:
            return None

        try:
            timestamp_str = state_transition_reason.split("(")[-1].strip(")")
            stopped_time = parser.parse(timestamp_str).astimezone(timezone.utc)
            return (current_time - stopped_time).days
        except Exception as e:
            logger.warning(f"Could not parse timestamp from {state_transition_reason}: {e}")
            return None

    def _analyze_instance_usage(self, params):
        """Analyze EC2 instance usage for underutilization over the last DAYS_THRESHOLD days."""
        session = params["session"]
        instance = params["instance"]
        current_time = params["current_time"]

        launch_time = instance["LaunchTime"]
        days_since_launch = (current_time - launch_time).days
        start_time = launch_time if days_since_launch < DAYS_THRESHOLD else current_time - timedelta(days=DAYS_THRESHOLD)

        instance_id = instance["InstanceId"]
        cloudwatch_client = session.get_client("cloudwatch")

        # Fetch CPU Usage (list of values over the last DAYS_THRESHOLD days)
        cpu_usage = fetch_metric(cloudwatch_client, "AWS/EC2", instance_id, "InstanceId", "CPUUtilization", "Average", start_time, current_time)

        # Fetch Network Traffic (list of values for NetworkPacketsIn and NetworkPacketsOut)
        network_in = fetch_metric(cloudwatch_client, "AWS/EC2", instance_id, "InstanceId", "NetworkPacketsIn", "Sum", start_time, current_time)
        network_out = fetch_metric(cloudwatch_client, "AWS/EC2", instance_id, "InstanceId", "NetworkPacketsOut", "Sum", start_time, current_time)

        # Fetch Disk I/O (list of values for VolumeReadOps and VolumeWriteOps)
        ebs_read_ops = fetch_metric(cloudwatch_client, "AWS/EBS", instance_id, "VolumeId", "VolumeReadOps", "Sum", start_time, current_time)
        ebs_write_ops = fetch_metric(cloudwatch_client, "AWS/EBS", instance_id, "VolumeId", "VolumeWriteOps", "Sum", start_time, current_time)

        # Analyze metrics to assess usage over the last DAYS_THRESHOLD days
        reasons = []

        # CPU Usage Analysis (e.g., low CPU usage)
        if len(cpu_usage) > 0:
            cpu_avg = np.mean(cpu_usage)  # Calculate the average CPU usage over the period
            if cpu_avg < 2:  # Example threshold for low CPU usage
                reasons.append(f"Low CPU usage: {cpu_avg:.2f}% average over the last {DAYS_THRESHOLD} days")

        # Network Traffic Analysis (e.g., low network traffic could indicate underutilization)
        if len(network_in) > 0 and len(network_out) > 0:
            network_in_sum = sum(network_in)  # Sum of all incoming packets over the period
            network_out_sum = sum(network_out)  # Sum of all outgoing packets over the period

            # Threshold for low network traffic (e.g., less than 1 million packets)
            if network_in_sum < 1_000_000 and network_out_sum < 1_000_000:
                reasons.append(f"Low network traffic: {network_in_sum + network_out_sum} packets in and out over the last {DAYS_THRESHOLD} days")

        # Disk I/O Analysis (e.g., low disk operations)
        if len(ebs_read_ops) > 0 and len(ebs_write_ops) > 0:
            ebs_read_ops_sum = sum(ebs_read_ops)  # Sum of all read operations
            ebs_write_ops_sum = sum(ebs_write_ops)  # Sum of all write operations

            # Threshold for low disk I/O (e.g., less than 1000 operations)
            if ebs_read_ops_sum < 1000 and ebs_write_ops_sum < 1000:
                reasons.append(f"Low disk I/O: {ebs_read_ops_sum + ebs_write_ops_sum} disk operations over the last {DAYS_THRESHOLD} days")

        # Return the reasons for underutilization
        return reasons


    def _calculate_running_hours(self, launch_time):
        """Calculate the number of hours the instance has been running."""
        current_time = datetime.now(timezone.utc)

        # Ensure launch_time is in UTC if it's a naive datetime object
        if launch_time.tzinfo is None:
            launch_time = launch_time.replace(tzinfo=timezone.utc)  # If launch_time has no timezone, set it to UTC
        
        # Ensure current_time is in UTC
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        # Guard against future launch times
        if current_time < launch_time:
            logger.warning(f"Instance launch time is in the future: {launch_time}. Setting running hours to 0.")
            return 0

        # Calculate the running duration and convert it to hours
        running_duration = current_time - launch_time
        return max(running_duration.total_seconds() / 3600, 0)  # Convert seconds to hours and ensure no negative values

    def _get_ebs_volumes(self, session, instance):
        """Get the EBS volume types and sizes associated with the EC2 instance."""
        ebs_details = []
        hours_running = self._calculate_running_hours(instance.get("LaunchTime"))
        for block_device in instance.get("BlockDeviceMappings", []):
            if "Ebs" in block_device:
                volume_id = block_device["Ebs"]["VolumeId"]
                ebs_client = session.get_client("ec2")
                volume = ebs_client.describe_volumes(VolumeIds=[volume_id])["Volumes"][0]
                volume_type = volume.get("VolumeType", "Unknown")
                volume_size = volume.get("Size", 0)  # Size in GB
                ebs_details.append({"VolumeId": volume_id, "VolumeType": volume_type, "SizeGB": volume_size, "HoursRunning": hours_running})
        return ebs_details

    def _calculate_combined_costs(self, ebs_details, instance_class, hours_running):
        """Calculate the combined cost of the EC2 instance and associated EBS volumes."""
        instance_cost = self.cost_estimator.estimate_instance_cost(instance_class, hours_running)
        ebs_cost = self.cost_estimator.estimate_ebs_cost(ebs_details)
        return {"instance_cost": instance_cost, "ebs_cost": ebs_cost}
