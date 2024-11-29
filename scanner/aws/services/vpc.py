from utils.logger import get_logger
from scanner.resource_scanner_registry import ResourceScannerRegistry
from config.config import DAYS_THRESHOLD
from datetime import datetime, timedelta, timezone
import numpy as np  # For calculating standard deviation

logger = get_logger(__name__)

class VPCScanner(ResourceScannerRegistry):
    """
    Scanner for identifying unused VPCs or those with low traffic deviation.
    """
    argument_name = "vpcs"
    label = "VPCs"

    def __init__(self):
        super().__init__(name=__name__, argument_name=self.argument_name, label=self.label)

    def scan(self, session, *args, **kwargs):
        """
        Retrieve and scan all VPCs for unused resources or low traffic deviation.

        :param session: Boto3 session object for AWS API calls.
        :return: List of unused VPCs with details.
        """
        logger.debug("Starting scan for unused VPCs...")
        try:
            ec2_client = session.get_client("ec2")
            cloudwatch_client = session.get_client("cloudwatch")
            vpcs = ec2_client.describe_vpcs()["Vpcs"]
            unused_vpcs = []

            for vpc in vpcs:
                vpc_id = vpc["VpcId"]
                vpc_name = next((tag["Value"] for tag in vpc.get("Tags", []) if tag["Key"] == "Name"), vpc_id)
                is_default = vpc.get("IsDefault", False)

                logger.debug(f"Scanning VPC {vpc_id}...")

                if is_default:
                    logger.debug(f"Skipping default VPC {vpc_id}.")
                    continue

                # Scan the VPC for unused resources or low traffic deviation
                unused_vpc = self.get_unused_vpc_resources(
                    ec2_client, cloudwatch_client, session.account_id, vpc_id, vpc_name
                )

                if unused_vpc:
                    unused_vpcs.append(unused_vpc)

            logger.info(f"Found {len(unused_vpcs)} unused VPCs.")
            return unused_vpcs

        except Exception as e:
            logger.error(f"Error during VPC scan: {e}")
            return []

    def get_unused_vpc_resources(self, ec2_client, cloudwatch_client, account_id, vpc_id, vpc_name):
        """
        Scan a specific VPC for unused resources or low traffic deviation.

        :param ec2_client: EC2 client for AWS API calls.
        :param cloudwatch_client: CloudWatch client for metrics.
        :param account_id: AWS account ID.
        :param vpc_id: VPC ID to scan.
        :param vpc_name: VPC Name for identification.
        :return: A dictionary of VPC details if it's unused, else None.
        """
        logger.debug(f"Scanning VPC {vpc_id} for unused resources or low traffic deviation...")

        try:
            # Fetch all resources in the VPC (subnets, instances, etc.)
            instances = ec2_client.describe_instances(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["Reservations"]
            resource_count = sum([len(res["Instances"]) for res in instances])

            # If there are no resources, skip traffic calculation and immediately return the VPC as unused
            if resource_count == 0:
                logger.debug(f"VPC {vpc_id} has no resources. Marking as unused.")
                return {
                    "VPCId": vpc_id,
                    "Name": vpc_name,
                    "Resources": resource_count,
                    "Traffic": 0,
                    "AccountId": account_id,
                    "Reason": "No Resources"
                }

            # Initialize traffic data
            traffic_data = []

            # Define the time range for the traffic query (e.g., last 90 days)
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(days=DAYS_THRESHOLD)

            # Fetch metric data with the correct parameters
            metric_data = cloudwatch_client.get_metric_data(
                MetricDataQueries=[{
                    'Id': 'trafficQuery',
                    'MetricStat': {
                        'Metric': {
                            'Namespace': 'AWS/EC2',
                            'MetricName': 'NetworkPacketsIn',
                            'Dimensions': [{'Name': 'VpcId', 'Value': vpc_id}]
                        },
                        'Period': 3600,  # 1 hour
                        'Stat': 'Sum'
                    },
                    'ReturnData': True
                }],
                StartTime=start_time,
                EndTime=end_time
            )

            # Collect traffic data points
            traffic_data = [point['Sum'] for point in metric_data['MetricDataResults'][0]['Values']]

            logger.debug(f"VPC {vpc_id} scan complete. Resources: {resource_count}, Traffic data points: {len(traffic_data)}.")

            # Calculate the average and deviation of traffic
            if len(traffic_data) > 1:
                avg_traffic = np.mean(traffic_data)
                std_deviation = np.std(traffic_data)

                # Check if the current traffic deviation is within the acceptable range
                current_traffic = traffic_data[-1]  # Last data point
                deviation = abs(current_traffic - avg_traffic) / avg_traffic  # Relative deviation

                logger.debug(f"VPC {vpc_id} traffic analysis: Average Traffic: {avg_traffic}, Current Traffic: {current_traffic}, Deviation: {deviation}")

                if deviation < 0.5:  # If the deviation is very low, consider it as low traffic
                    reason = f"Low traffic deviation: {deviation:.2%} from average"
                else:
                    reason = None
            else:
                reason = None

            if reason:
                return {
                    "VPCId": vpc_id,
                    "Name": vpc_name,
                    "Resources": resource_count,
                    "Traffic": sum(traffic_data),
                    "AccountId": account_id,
                    "Reason": reason
                }
            else:
                return None

        except Exception as e:
            logger.error(f"Error scanning VPC {vpc_id}: {e}")
            return {
                "VPCId": vpc_id,
                "Error": str(e),
                "Reason": f"Error occurred while scanning VPC: {e}"
            }
