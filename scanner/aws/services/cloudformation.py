from datetime import datetime, timezone
from utils.logger import get_logger
from config.config import DAYS_THRESHOLD
from scanner.resource_scanner_registry import ResourceScannerRegistry
from scanner.aws.utils.scanner_helper import determine_metric_time_window, fetch_metric, determine_unused_reason

logger = get_logger(__name__)

class CloudFormationScanner(ResourceScannerRegistry):
    """
    Scanner for CloudFormation stacks.
    """
    argument_name = "cloudformation"
    label = "Cloud Formation Stacks"

    def __init__(self):
        super().__init__(name=__name__, argument_name=self.argument_name, label=self.label)

    def scan(self, session, *args, **kwargs):
        """Retrieve and check for unused CloudFormation stack resources."""
        logger.debug("Retrieving CloudFormation stacks...")
        try:
            cfn_client = session.get_client("cloudformation")
            cloudwatch_client = session.get_client("cloudwatch")
            stacks = cfn_client.describe_stacks()["Stacks"]
            unused_resources = []
            current_time = datetime.now(timezone.utc)

            for stack in stacks:
                stack_name = stack["StackName"]
                stack_status = stack["StackStatus"]
                logger.debug(f"Processing stack: {stack_name} (Status: {stack_status})")

                if stack_status in ["DELETE_COMPLETE", "ROLLBACK_COMPLETE"]:
                    unused_resources.append({
                        "ResourceName": stack_name,
                        "ResourceId": stack_name,
                        "Reason": f"Stack is in terminal state ({stack_status}).",
                        "AccountId": session.account_id,
                    })
                    continue

                resources = cfn_client.list_stack_resources(StackName=stack_name)["StackResourceSummaries"]
                for resource in resources:
                    resource_id = resource["PhysicalResourceId"]
                    resource_type = resource.get("ResourceType")
                    resource_status = resource["ResourceStatus"]

                    if resource_type != "AWS::EC2::Instance" or resource_status in ["DELETE_COMPLETE", "ROLLBACK_COMPLETE"]:
                        continue

                    start_time = determine_metric_time_window(stack["CreationTime"], current_time, DAYS_THRESHOLD)
                    resource_usage = self.check_instance_usage(cloudwatch_client, resource_id, start_time, current_time)

                    reason = resource_usage.get("reason")
                    if reason:
                        unused_resources.append({
                            "ResourceName": stack_name,
                            "ResourceId": resource_id,
                            "ResourceType": resource_type,
                            "Reason": reason,
                        })

            logger.info(f"Found {len(unused_resources)} unused CloudFormation resources.")
            return unused_resources
        except Exception as e:
            logger.error(f"Error retrieving CloudFormation resources: {e}")
            return []

    def check_instance_usage(self, cloudwatch_client, instance_id, start_time, end_time):
        """Check the EC2 instance's usage metrics."""
        
        # Fetch metrics using the new fetch_metric function (returns a list of values)
        metrics = {
            "cpu": fetch_metric(
                cloudwatch_client, "AWS/EC2", instance_id, "InstanceId", "CPUUtilization", "Average", start_time, end_time
            ),
            "network": fetch_metric(
                cloudwatch_client, "AWS/EC2", instance_id, "InstanceId", "NetworkPacketsIn", "Sum", start_time, end_time
            ),
        }
        
        # Sum the values from the lists returned by fetch_metric
        cpu_usage_total = sum(metrics["cpu"])  # Sum the CPU utilization values
        network_usage_total = sum(metrics["network"])  # Sum the network packets in values

        unused_conditions = [
            (lambda m: (cpu_usage_total == 0, "No CPU usage detected.")),
            (lambda m: (network_usage_total == 0, "No network activity detected.")),
        ]
        
        reason = determine_unused_reason(metrics, unused_conditions)
        if reason:
            metrics["reason"] = reason
        
        return metrics