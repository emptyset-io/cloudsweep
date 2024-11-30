from datetime import datetime, timezone
from utils.logger import get_logger
from config.config import DAYS_THRESHOLD
from scanner.resource_scanner_registry import ResourceScannerRegistry
from scanner.aws.utils.scanner_helper import (
    determine_metric_time_window,
    fetch_metric
)

logger = get_logger(__name__)

class S3Scanner(ResourceScannerRegistry):
    """
    Scanner for identifying unused S3 buckets.
    """
    argument_name = "s3"
    label = "S3 Buckets"

    def __init__(self):
        super().__init__(name=__name__, argument_name=self.argument_name, label=self.label)

    def scan(self, session, *args, **kwargs):
        """
        Retrieve and identify unused S3 buckets based on object count and historical activity.

        :param session: Boto3 session object for AWS API calls.
        :return: List of unused S3 buckets with details.
        """
        logger.debug("Starting scan for unused S3 buckets...")
        try:
            s3_client = session.get_client("s3")
            cloudwatch_client = session.get_client("cloudwatch")
            region = session.region_name
            response = s3_client.list_buckets()
            buckets = response.get("Buckets", [])
            unused_buckets = []
            current_time = datetime.now(timezone.utc)

            for bucket in buckets:
                bucket_name = bucket["Name"]
                creation_date = bucket["CreationDate"]
                bucket_arn = f"arn:aws:s3:::{bucket_name}"

                # Retrieve the region for the current bucket
                try:
                    region_response = s3_client.get_bucket_location(Bucket=bucket_name)
                    bucket_region = region_response.get("LocationConstraint", "us-east-1")
                except Exception as e:
                    logger.error(f"Could not retrieve region for bucket {bucket_name}: {e}")
                    continue

                if bucket_region != region:
                    logger.debug(f"Skipping bucket {bucket_name} (region: {bucket_region}) as it does not match {region}.")
                    continue

                logger.debug(f"Checking S3 bucket {bucket_name} for usage in region {region}...")

                # Current object count
                current_object_count = self._get_bucket_object_count(s3_client, bucket_name)

                # Historical object count
                start_time = determine_metric_time_window(creation_date, current_time, DAYS_THRESHOLD)
                previous_object_count = fetch_metric(
                    cloudwatch_client, 
                    namespace="AWS/S3", 
                    resource_name=bucket_name, 
                    dimension_name="BucketName", 
                    metric_name="NumberOfObjects", 
                    stat="Average", 
                    start_time=start_time, 
                    end_time=current_time
                )

                # Determine reasons for marking the bucket as unused
                reasons = []
                if current_object_count == 0:
                    reasons.append("No objects in bucket.")
                if current_object_count == previous_object_count:
                    reasons.append(f"No change in object count over the last {DAYS_THRESHOLD} days.")

                if reasons:
                    unused_buckets.append({
                        "ResourceName": bucket_name,
                        "ResourceId": bucket_arn,
                        "ObjectCount": current_object_count,
                        "AccountId": session.account_id,
                        "Region": bucket_region,
                        "Reason": "\n".join(reasons),
                    })

            logger.info(f"Found {len(unused_buckets)} unused S3 buckets in region {region}.")
            return unused_buckets
        except Exception as e:
            logger.error(f"Error during S3 scan: {e}")
            return []

    @staticmethod
    def _get_bucket_object_count(s3_client, bucket_name):
        """
        Get the current number of objects in the S3 bucket.

        :param s3_client: Boto3 S3 client.
        :param bucket_name: Name of the bucket.
        :return: Object count or 0 if unable to retrieve.
        """
        logger.debug(f"Getting object count for bucket {bucket_name}...")
        try:
            response = s3_client.list_objects_v2(Bucket=bucket_name)
            return response.get("KeyCount", 0)
        except Exception as e:
            logger.error(f"Error getting object count for bucket {bucket_name}: {e}")
            return 0
