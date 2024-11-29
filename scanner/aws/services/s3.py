from datetime import datetime, timedelta, timezone
from utils.logger import get_logger
from config.config import DAYS_THRESHOLD
from scanner.resource_scanner_registry import ResourceScannerRegistry

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
                bucket_arn = f"arn:aws:s3:::{bucket_name}"  # Construct the ARN for the bucket

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

                reason = []
                current_object_count = self._get_bucket_object_count(s3_client, bucket_name)

                if current_object_count == 0:
                    reason.append("No objects in bucket.")

                # Check historical object count
                start_time = current_time - timedelta(days=DAYS_THRESHOLD)
                previous_object_count = self._get_object_count_from_cloudwatch(cloudwatch_client, bucket_name, start_time, current_time)

                if current_object_count == previous_object_count:
                    reason.append(f"No change in object count over the {DAYS_THRESHOLD} day threshold period.")

                if reason:
                    unused_buckets.append({
                        "BucketName": bucket_name,
                        "BucketArn": bucket_arn,
                        "ObjectCount": current_object_count,
                        "AccountId": session.account_id,
                        "Region": bucket_region,
                        "Reason": "\n".join(reason)
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

    @staticmethod
    def _get_object_count_from_cloudwatch(cloudwatch_client, bucket_name, start_time, end_time):
        """
        Retrieve the historical number of objects in the S3 bucket using CloudWatch metrics.

        :param cloudwatch_client: Boto3 CloudWatch client.
        :param bucket_name: Name of the bucket.
        :param start_time: Start of the time range.
        :param end_time: End of the time range.
        :return: Object count from CloudWatch or -1 if unable to retrieve.
        """
        logger.debug(f"Getting historical object count for bucket {bucket_name} from CloudWatch...")
        try:
            response = cloudwatch_client.get_metric_data(
                MetricDataQueries=[{
                    'Id': 'objectCount',
                    'MetricStat': {
                        'Metric': {
                            'Namespace': 'AWS/S3',
                            'MetricName': 'NumberOfObjects',
                            'Dimensions': [{'Name': 'BucketName', 'Value': bucket_name}]
                        },
                        'Period': 86400,  # Daily metrics
                        'Stat': 'Average'
                    },
                    'ReturnData': True
                }],
                StartTime=start_time,
                EndTime=end_time
            )

            data_points = response['MetricDataResults'][0]['Values']
            return data_points[0] if data_points else 0
        except Exception as e:
            logger.error(f"Error retrieving historical object count for bucket {bucket_name}: {e}")
            return -1
