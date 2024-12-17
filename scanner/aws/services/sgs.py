from utils.logger import get_logger
from scanner.resource_scanner_registry import ResourceScannerRegistry
from scanner.aws.utils.scanner_helper import extract_tag_value

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
                    
                    # Use the extract_tag_value helper to get the 'Name' tag value if available
                    resource_name = extract_tag_value(sg.get("Tags", []), "Name", sg["GroupName"])

                    # Add the ResourceName and ResourceId (SecurityGroupId) to the security group details
                    unused_groups.append({
                        "ResourceName": resource_name,
                        "ResourceId": sg["GroupId"],
                        "Reason": sg["Reason"]
                    })

            logger.info(f"Found {len(unused_groups)} unused Security Groups.")
            return unused_groups

        except Exception as e:
            logger.error(f"Error during security group scan: {e}")
            return []
