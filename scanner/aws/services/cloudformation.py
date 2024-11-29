from datetime import datetime, timedelta, timezone
from utils.logger import get_logger
from config.config import DAYS_THRESHOLD
from scanner.resource_scanner_registry import ResourceScannerRegistry

logger = get_logger(__name__)

class CloudFormationScanner(ResourceScannerRegistry):
    """
    Scanner for CloudFormation stacks.
    """
    # Define the attributes:
    argument_name = "cloudformation"  # The short name for user arguments
    label = "Cloud Formation Stacks"  # The label used in reports

    def __init__(self):
        super().__init__(name=__name__, argument_name=self.argument_name, label=self.label)  # Pass the class-level attributes to the parent

    def scan(self, session, *args, **kwargs):
        """
        Retrieve and check for unused CloudFormation stack resources.

        :param session: Boto3 session object for AWS API calls.
        :param session.account_id: AWS account ID.
        :return: List of unused resources.
        """
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
                    logger.debug(f"Stack {stack_name} is in a terminal state. Marking as unused.")
                    unused_resources.append({
                        "StackName": stack_name,
                        "Reason": f"Stack is in terminal state ({stack_status}).",
                        "AccountId": session.account_id
                    })
                    continue

                # Get stack resources
                resources = cfn_client.list_stack_resources(StackName=stack_name)["StackResourceSummaries"]
                for resource in resources:
                    resource_id = resource["PhysicalResourceId"]
                    resource_type = resource.get("ResourceType")
                    resource_status = resource["ResourceStatus"]

                    # Filter for EC2 instances
                    if resource_type != "AWS::EC2::Instance":
                        continue

                    if resource_status in ["DELETE_COMPLETE", "ROLLBACK_COMPLETE"]:
                        logger.debug(f"Resource {resource_id} in stack {stack_name} is unused.")
                        unused_resources.append({
                            "StackName": stack_name,
                            "ResourceId": resource_id,
                            "Reason": f"Resource is in terminal state ({resource_status}).",
                            "AccountId": session.account_id
                        })
                    else:
                        # Perform usage checks for specific resource types (e.g., EC2, RDS)
                        launch_time = stack["CreationTime"]
                        days_since_launch = (current_time - launch_time).days

                        # Determine the start time for metrics based on launch time
                        if days_since_launch < DAYS_THRESHOLD:
                            start_time = launch_time
                        else:
                            start_time = current_time - timedelta(days=DAYS_THRESHOLD)

                        #Uncomment to add usage checks (like CloudWatch metrics)
                        resource_usage = self.check_instance_usage(cloudwatch_client, resource_id, start_time, current_time)
                        if resource_usage.get("unused"):
                            unused_resources.append({
                                "StackName": stack_name,
                                "ResourceId": resource_id,
                                "ResourceType": resource_type,
                                "Reason": resource_usage["reason"],
                                "AccountId": session.account_id
                            })
                            logger.debug(f"Resource {resource_id} in stack {stack_name} is unused: {resource_usage['reason']}")

            logger.info(f"Found {len(unused_resources)} unused CloudFormation resources.")
            return unused_resources
        except Exception as e:
            logger.error(f"Error retrieving CloudFormation resources: {e}")
            return []

    def check_instance_usage(self, cloudwatch_client, instance_id, start_time, end_time):
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
