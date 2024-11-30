from utils.logger import get_logger
from scanner.resource_scanner_registry import ResourceScannerRegistry

logger = get_logger(__name__)

class EipScanner(ResourceScannerRegistry):
    """
    Scanner for Elastic IPs.
    """
    argument_name = "elastic-ips"
    label = "Elastic IPs"

    def __init__(self):
        super().__init__(name=__name__, argument_name=self.argument_name, label=self.label)

    def scan(self, session, *args, **kwargs):
        """Retrieve unused Elastic IPs."""
        logger.debug("Retrieving unused Elastic IPs...")
        try:
            ec2_client = session.get_client("ec2")
            addresses = ec2_client.describe_addresses()["Addresses"]
            unused_ips = []

            for addr in addresses:
                allocation_id = addr.get("AllocationId")
                public_ip = addr.get("PublicIp")
                logger.debug(f"Checking Elastic IP {public_ip} for usage...")

                # Check if the Elastic IP is not associated with any resource
                if "InstanceId" not in addr and "NetworkInterfaceId" not in addr:
                    if not self._check_nat_gateway_association(ec2_client, allocation_id):
                        unused_ips.append({
                            "ResourceId": allocation_id,
                            "ResourceName": public_ip,
                            "AccountId": session.account_id,
                            "Name": public_ip,  # Use PublicIp as a display name
                            "Reason": "Not associated with any resource (EC2 Instance, Network Interface, or NAT Gateway)."
                        })
                        logger.debug(f"Elastic IP {public_ip} is unused and added to the list.")

            logger.info(f"Found {len(unused_ips)} unused Elastic IPs.")
            return unused_ips

        except Exception as e:
            logger.error(f"Error retrieving Elastic IPs: {e}")
            return []
    
    def _check_nat_gateway_association(self, ec2_client, allocation_id):
        """Check if an Elastic IP is associated with a NAT Gateway."""
        if not allocation_id:
            logger.debug("No Allocation ID provided for NAT Gateway association check.")
            return False

        logger.debug(f"Checking NAT Gateway association for Allocation ID {allocation_id}...")
        try:
            nat_gateways = ec2_client.describe_nat_gateways()["NatGateways"]

            for nat_gateway in nat_gateways:
                for address in nat_gateway.get("NatGatewayAddresses", []):
                    if address.get("AllocationId") == allocation_id:
                        logger.debug(f"Elastic IP with Allocation ID {allocation_id} is associated with NAT Gateway {nat_gateway['NatGatewayId']}.")
                        return True

            return False
        except Exception as e:
            logger.error(f"Error checking NAT Gateway association for Allocation ID {allocation_id}: {e}")
            return False
