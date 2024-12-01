from datetime import datetime, timezone
from utils.logger import get_logger
from config.config import DAYS_THRESHOLD
from scanner.resource_scanner_registry import ResourceScannerRegistry
from scanner.aws.utils.scanner_helper import extract_tag_value
from scanner.aws.cost_estimator import CostEstimator

logger = get_logger(__name__)

class EbsSnapshotScanner(ResourceScannerRegistry):
    """
    Scanner for EBS Snapshots.
    """
    argument_name = "ebs-snapshots"
    label = "EBS Snapshots"

    def __init__(self):
        super().__init__(name=__name__, argument_name=self.argument_name, label=self.label)

    def scan(self, session, *args, **kwargs):
        """Retrieve EBS snapshots and check for unused snapshots."""
        logger.debug("Retrieving EBS snapshots...")
        try:
            ec2_client = session.get_client("ec2")
            snapshots = ec2_client.describe_snapshots(OwnerIds=["self"])["Snapshots"]
            unused_snapshots = []
            current_time = datetime.now(timezone.utc)

            for snapshot in snapshots:
                snapshot_id = snapshot["SnapshotId"]
                logger.debug(f"Checking EBS snapshot {snapshot_id} for usage...")

                # Retrieve snapshot description or tags for a name
                snapshot_name = extract_tag_value(snapshot.get("Tags"), key="Name")
                snapshot_description = snapshot.get("Description", "N/A")
                create_time = snapshot["StartTime"]
                size_in_gb = snapshot["VolumeSize"]

                # Calculate snapshot age
                days_since_creation = (current_time - create_time).days
                age_in_hours = int((current_time - create_time).total_seconds() / 3600)

                # Estimate snapshot cost
                cost_details = CostEstimator().calculate_cost(
                    resource_type="EBS-Snapshots",
                    resource_size=size_in_gb,
                    hours_running=age_in_hours,
                )

                # Mark snapshot as unused if older than threshold
                if days_since_creation >= DAYS_THRESHOLD:
                    unused_snapshots.append({
                        "ResourceName": snapshot_name or snapshot_description,
                        "ResourceId": snapshot_id,
                        "Size": size_in_gb,
                        "CreateTime": create_time,
                        "AccountId": session.account_id,
                        "Reason": f"Snapshot is {days_since_creation} days old, exceeding the threshold of {DAYS_THRESHOLD} days",
                        "Cost": {self.label: cost_details}
                    })
                    logger.debug(f"EBS snapshot[{snapshot_id}] cost: {cost_details}")
                    logger.info(f"EBS snapshot {snapshot_id} ({snapshot_name or snapshot_description}) is unused.")

            logger.info(f"Found {len(unused_snapshots)} unused EBS snapshots.")
            return unused_snapshots

        except Exception as e:
            logger.error(f"Error retrieving EBS snapshots: {e}")
            return []
