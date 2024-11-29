from utils.logger import get_logger
from scanner.resource_scanner_registry import ResourceScannerRegistry

logger = get_logger(__name__)

class SecurityGroupScanner(ResourceScannerRegistry):
    """
    Scanner for identifying unused Security Groups.
    """
    argument_name = "security-groups"
    label = "Security Groups"

    def __init__(self):
        super().__init__(name=__name__, argument_name=self.argument_name, label=self.label)

    def scan(self, session, *args, **kwargs):
        """
        Retrieve and identify unused security groups based on network interface associations.

        :param session: Boto3 session object for AWS API calls.
        :return: List of unused security groups with details.
        """
        logger.debug("Starting scan for unused Security Groups...")
        try:
            ec2_client = session.get_client("ec2")
            security_groups = ec2_client.describe_security_groups()["SecurityGroups"]
            unused_groups = []

            for sg in security_groups:
                if sg["GroupName"] == "default":
                    continue

                # Check if the security group is associated with any resources
                sg_associations = ec2_client.describe_network_interfaces(Filters=[{
                    "Name": "group-id",
                    "Values": [sg["GroupId"]]
                }])["NetworkInterfaces"]

                if not sg_associations:
                    sg["Reason"] = "Not associated with any resource (EC2 Instance or ENI)."
                    unused_groups.append(sg)

            # Add additional information to the unused security groups
            for sg in unused_groups:
                sg["AccountId"] = session.account_id
                sg["Name"] = sg.get("GroupName")
                logger.debug(f"Security Group {sg['GroupId']} added with Account ID {session.account_id} and Reason: {sg['Reason']}")

            logger.info(f"Found {len(unused_groups)} unused Security Groups.")
            return unused_groups

        except Exception as e:
            logger.error(f"Error during security group scan: {e}")
            return []
