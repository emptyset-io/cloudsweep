from datetime import datetime, timezone
from utils.logger import get_logger
from config.config import DAYS_THRESHOLD
from scanner.resource_scanner_registry import ResourceScannerRegistry
from scanner.aws.utils.scanner_helper import extract_tag_value

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
                logger.debug(f"Checking EBS snapshot {snapshot_id}...")

                # Extract snapshot name from tags
                snapshot_name = extract_tag_value(snapshot.get("Tags", []), "Name")

                # Determine snapshot age and unused status
                start_time = snapshot["StartTime"]
                if (current_time - start_time).days >= DAYS_THRESHOLD:
                    unused_snapshots.append({
                        "ResourceName": snapshot_name,
                        "ResourceId": snapshot_id,
                        "State": snapshot["State"],
                        "VolumeId": snapshot.get("VolumeId", "N/A"),
                        "VolumeSize": snapshot.get("VolumeSize", 0),  # Size in GiB
                        "StartTime": start_time,
                        "AccountId": session.account_id,
                        "Reason": f"Snapshot has not been accessed for "
                                  f"{(current_time - start_time).days} days, "
                                  f"exceeding the threshold of {DAYS_THRESHOLD} days"
                    })
                    logger.info(f"EBS snapshot {snapshot_id} ({snapshot_name}) is unused.")

            logger.info(f"Found {len(unused_snapshots)} unused EBS snapshots.")
            return unused_snapshots

        except Exception as e:
            logger.error(f"Error retrieving EBS snapshots: {e}")
            return []
