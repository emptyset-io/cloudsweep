from datetime import datetime, timezone
from utils.logger import get_logger
from config.config import DAYS_THRESHOLD
from scanner.resource_scanner_registry import ResourceScannerRegistry
from scanner.aws.utils.scanner_helper import extract_tag_value
from scanner.aws.cost_estimator import CostEstimator

logger = get_logger(__name__)

class EbsVolumeScanner(ResourceScannerRegistry):
    """
    Scanner for EBS Volumes.
    """
    argument_name = "ebs-volumes"
    label = "EBS Volumes"

    def __init__(self):
        super().__init__(name=__name__, argument_name=self.argument_name, label=self.label)

    def scan(self, session, *args, **kwargs):
        """Retrieve EBS volumes and check for unused volumes."""
        logger.debug("Retrieving EBS volumes...")
        try:
            ec2_client = session.get_client("ec2")
            volumes = ec2_client.describe_volumes()["Volumes"]
            unused_volumes = []
            current_time = datetime.now(timezone.utc)

            for volume in volumes:
                volume_id = volume["VolumeId"]
                logger.debug(f"Checking EBS volume {volume_id} for usage...")

                # Retrieve volume name using helper function
                volume_name = extract_tag_value(volume.get("Tags"), key="Name")

                # Check if the volume is unattached
                if not volume["Attachments"]:
                    create_time = volume["CreateTime"]
                    days_since_creation = (current_time - create_time).days
                     # Calculate age in hours
                    age_in_hours = int((current_time - create_time).total_seconds() / 3600)
                    cost_details = CostEstimator().calculate_cost(
                        resource_type=self.label,
                        resource_size=volume["Size"],
                        hours_running=age_in_hours
                    )

                    # Mark volume as unused if it's older than the threshold
                    if days_since_creation >= DAYS_THRESHOLD:
                        unused_volumes.append({
                            "ResourceName": volume_name,
                            "ResourceId": volume_id,
                            "State": volume["State"],
                            "Size": volume["Size"],  # Size in GiB
                            "CreateTime": create_time,
                            "AccountId": session.account_id,
                            "Reason": f"Volume has been unattached for {days_since_creation} days, exceeding the threshold of {DAYS_THRESHOLD} days",
                            "Cost": {self.label: cost_details}
                        })
                        logger.debug(f"EBS volume[{volume_id}] cost: {cost_details}")
                        logger.info(f"EBS volume {volume_id} ({volume_name}) is unused.")

            logger.info(f"Found {len(unused_volumes)} unused EBS volumes.")
            return unused_volumes

        except Exception as e:
            logger.error(f"Error retrieving EBS volumes: {e}")
            return []
