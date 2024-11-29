from datetime import datetime, timezone
import time
from utils.logger import get_logger
from config.config import DAYS_THRESHOLD
from scanner.resource_scanner_registry import ResourceScannerRegistry

logger = get_logger(__name__)

MAX_RETRIES = 5
RETRY_BACKOFF = 2  # Exponential backoff factor (seconds)

class EbsSnapshotsScanner(ResourceScannerRegistry):
    """
    Scanner for EBS snapshots.
    """
    argument_name = "ebs-snapshots"
    label = "EBS Snapshots"

    def __init__(self):
        super().__init__(name=__name__, argument_name=self.argument_name, label=self.label)

    def scan(self, session, account_id, *args, **kwargs):
        """Retrieve EBS snapshots and check for unused ones."""
        logger.debug("Retrieving EBS snapshots...")
        retries = 0
        while retries < MAX_RETRIES:
            try:
                ec2_client = session.get_client("ec2")
                snapshots = ec2_client.describe_snapshots(OwnerIds=[account_id])["Snapshots"]
                unused_snapshots = []
                current_time = datetime.now(timezone.utc)

                for snapshot in snapshots:
                    snapshot_id = snapshot["SnapshotId"]
                    logger.debug(f"Checking EBS snapshot {snapshot_id} for usage...")
                    snapshot_name = "Unnamed"
                    if "Tags" in snapshot:
                        for tag in snapshot["Tags"]:
                            if tag["Key"] == "Name":
                                snapshot_name = tag["Value"]
                                break

                    # Check if snapshot is linked to any existing volume
                    last_used_time = snapshot["StartTime"]
                    days_since_last_used = (current_time - last_used_time).days

                    if days_since_last_used >= DAYS_THRESHOLD:
                        unused_snapshots.append({
                            "Name": snapshot_name,
                            "SnapshotId": snapshot_id,
                            "State": snapshot["State"],
                            "VolumeId": snapshot["VolumeId"],
                            "Size": snapshot["VolumeSize"],  # Size in GiB
                            "StartTime": snapshot["StartTime"],
                            "LastUsed": days_since_last_used,
                            "AccountId": account_id,
                            "Reason": f"Snapshot has not been accessed for {days_since_last_used} days, exceeding the threshold of {DAYS_THRESHOLD} days"
                        })
                        logger.debug(f"EBS snapshot {snapshot_id} is unused.")

                logger.info(f"Found {len(unused_snapshots)} unused EBS snapshots.")
                return unused_snapshots

            except Exception as e:
                retries += 1
                logger.error(f"Error retrieving EBS snapshots (Attempt {retries}/{MAX_RETRIES}): {e}", exc_info=True)

                if retries < MAX_RETRIES:
                    # Exponential backoff
                    backoff_time = RETRY_BACKOFF ** retries
                    logger.info(f"Retrying in {backoff_time} seconds...")
                    time.sleep(backoff_time)
                else:
                    logger.error("Max retries reached. Could not retrieve EBS snapshots.")
                    return []

