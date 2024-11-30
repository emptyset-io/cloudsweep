from utils.logger import get_logger
from scanner.resource_scanner_registry import ResourceScannerRegistry
from scanner.aws.utils.scanner_helper import extract_tag_value
from config.config import DAYS_THRESHOLD
from datetime import datetime, timezone, timedelta

logger = get_logger(__name__)

class VPCScanner(ResourceScannerRegistry):
    """
    Scanner for identifying unused VPCs.
    """
    argument_name = "vpcs"
    label = "VPCs"

    def __init__(self):
        super().__init__(name=__name__, argument_name=self.argument_name, label=self.label)

    def scan(self, session, *args, **kwargs):
        """
        Retrieve and scan all VPCs for unused resources.

        :param session: Boto3 session object for AWS API calls.
        :return: List of unused VPCs with details.
        """
        logger.debug("Starting scan for unused VPCs...")
        try:
            ec2_client = session.get_client("ec2")
            vpcs = ec2_client.describe_vpcs()["Vpcs"]
            unused_vpcs = []

            for vpc in vpcs:
                vpc_id = vpc["VpcId"]
                vpc_name = extract_tag_value(vpc.get("Tags", []), "Name", vpc_id)
                is_default = vpc.get("IsDefault", False)

                logger.debug(f"Scanning VPC {vpc_id}...")

                if is_default:
                    logger.debug(f"Skipping default VPC {vpc_id}.")
                    continue

                # Scan the VPC for unused resources
                unused_vpc = self._analyze_vpc(ec2_client, session.account_id, vpc)

                if unused_vpc:
                    unused_vpcs.append(unused_vpc)

            logger.info(f"Found {len(unused_vpcs)} unused VPCs.")
            return unused_vpcs

        except Exception as e:
            logger.error(f"Error during VPC scan: {e}")
            return []

    def _analyze_vpc(self, ec2_client, account_id, vpc_details):
        """
        Analyze a specific VPC for unused resources.
        """
        try:
            vpc_id = vpc_details["VpcId"]
            vpc_name = vpc_details.get("Name", vpc_id)  # Default to VPC ID if no name exists

            # Fetch resource count
            resource_count = self._get_vpc_resource_count(ec2_client, vpc_id)

            # If there are no resources, mark the VPC as unused
            if resource_count == 0:
                logger.debug(f"VPC {vpc_id} has no resources. Marking as unused.")
                return {"ResourceId": vpc_id, "ResourceName": vpc_name, "Resources": resource_count, "AccountId": account_id, "Reason": "No Resources"}

            return None

        except Exception as e:
            logger.error(f"Error analyzing VPC {vpc_details['VpcId']}: {e}")
            return {"VPCId": vpc_details["VpcId"], "Error": str(e), "Reason": f"Error occurred while analyzing VPC: {e}"}

    def _get_vpc_resource_count(self, ec2_client, vpc_id):
        """
        Count the number of resources (e.g., EC2 instances) associated with a VPC.

        :param ec2_client: EC2 client for AWS API calls.
        :param vpc_id: VPC ID to scan.
        :return: Total number of resources associated with the VPC.
        """
        logger.debug(f"Counting resources for VPC {vpc_id}...")
        try:
            instances = ec2_client.describe_instances(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["Reservations"]
            return sum(len(res["Instances"]) for res in instances)
        except Exception as e:
            logger.error(f"Error counting resources for VPC {vpc_id}: {e}")
            return 0
