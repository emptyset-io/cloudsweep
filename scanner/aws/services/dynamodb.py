from datetime import datetime, timedelta, timezone
from utils.logger import get_logger
from config.config import DAYS_THRESHOLD
from scanner.resource_scanner_registry import ResourceScannerRegistry

logger = get_logger(__name__)

class DynamoDBScanner(ResourceScannerRegistry):
    """
    Scanner for DynamoDB tables.
    """
    argument_name = "dynamodb"
    label = "DynamoDB Tables"

    def __init__(self):
        super().__init__(name=__name__, argument_name=self.argument_name, label=self.label)

    def scan(self, session, *args, **kwargs):
        """Retrieve DynamoDB tables and check for usage based on key metrics."""
        logger.debug("Retrieving DynamoDB tables...")
        try:
            dynamodb_client = session.get_client("dynamodb")
            cloudwatch_client = session.get_client("cloudwatch")
            tables = dynamodb_client.list_tables()["TableNames"]
            unused_tables = []
            current_time = datetime.now(timezone.utc)

            for table_name in tables:
                logger.debug(f"Checking DynamoDB table {table_name} for usage...")

                # Retrieve table metadata
                table_info = dynamodb_client.describe_table(TableName=table_name)["Table"]
                creation_time = table_info["CreationDateTime"]
                days_since_creation = (current_time - creation_time).days

                # Determine the start time for metrics
                if days_since_creation < DAYS_THRESHOLD:
                    start_time = creation_time
                else:
                    start_time = current_time - timedelta(days=DAYS_THRESHOLD)

                # Check DynamoDB table usage
                table_usage = self.check_dynamodb_usage(cloudwatch_client, table_name, start_time, current_time)
                reason = None
                if table_usage.get("read_capacity") == 0 and table_usage.get("write_capacity") == 0:
                    reason = "No read or write activity."
                elif table_usage.get("throttled_events") > 0:
                    reason = f"Provisioned throughput exceeded events: {table_usage['throttled_events']}."

                if reason:
                    unused_tables.append({
                        "TableName": table_name,
                        "CreationDateTime": creation_time,
                        "ItemCount": table_info.get("ItemCount", 0),
                        "TableSizeBytes": table_info.get("TableSizeBytes", 0),
                        "AccountId": session.account_id,
                        "Reason": reason
                    })
                    logger.debug(f"DynamoDB table {table_name} is unused or underutilized: {reason}")

            logger.info(f"Found {len(unused_tables)} unused DynamoDB tables.")
            return unused_tables
        except Exception as e:
            logger.error(f"Error retrieving DynamoDB tables: {e}")
            return []

    def check_dynamodb_usage(self, cloudwatch_client, table_name, start_time, end_time):
        """Check the DynamoDB table's read/write capacity and throttled events metrics."""
        logger.debug(f"Checking usage for DynamoDB table {table_name} from {start_time} to {end_time}...")
        try:
            # Fetch Consumed Read Capacity
            read_capacity_metric = cloudwatch_client.get_metric_data(
                MetricDataQueries=[{
                    'Id': 'readCapacity',
                    'MetricStat': {
                        'Metric': {
                            'Namespace': 'AWS/DynamoDB',
                            'MetricName': 'ConsumedReadCapacityUnits',
                            'Dimensions': [{'Name': 'TableName', 'Value': table_name}]
                        },
                        'Period': 3600,
                        'Stat': 'Sum'
                    },
                    'ReturnData': True
                }],
                StartTime=start_time,
                EndTime=end_time
            )

            # Fetch Consumed Write Capacity
            write_capacity_metric = cloudwatch_client.get_metric_data(
                MetricDataQueries=[{
                    'Id': 'writeCapacity',
                    'MetricStat': {
                        'Metric': {
                            'Namespace': 'AWS/DynamoDB',
                            'MetricName': 'ConsumedWriteCapacityUnits',
                            'Dimensions': [{'Name': 'TableName', 'Value': table_name}]
                        },
                        'Period': 3600,
                        'Stat': 'Sum'
                    },
                    'ReturnData': True
                }],
                StartTime=start_time,
                EndTime=end_time
            )

            # Fetch Throttled Events
            throttled_events_metric = cloudwatch_client.get_metric_data(
                MetricDataQueries=[{
                    'Id': 'throttledEvents',
                    'MetricStat': {
                        'Metric': {
                            'Namespace': 'AWS/DynamoDB',
                            'MetricName': 'ProvisionedThroughputExceededEvents',
                            'Dimensions': [{'Name': 'TableName', 'Value': table_name}]
                        },
                        'Period': 3600,
                        'Stat': 'Sum'
                    },
                    'ReturnData': True
                }],
                StartTime=start_time,
                EndTime=end_time
            )

            # Extract metric values
            read_capacity_data = read_capacity_metric['MetricDataResults'][0]['Values']
            write_capacity_data = write_capacity_metric['MetricDataResults'][0]['Values']
            throttled_events_data = throttled_events_metric['MetricDataResults'][0]['Values']

            return {
                "read_capacity": sum(read_capacity_data) if read_capacity_data else 0,
                "write_capacity": sum(write_capacity_data) if write_capacity_data else 0,
                "throttled_events": sum(throttled_events_data) if throttled_events_data else 0
            }

        except Exception as e:
            logger.error(f"Error checking usage for DynamoDB table {table_name}: {e}")
            return {"read_capacity": 0, "write_capacity": 0, "throttled_events": 0}  # Default to unused if error occurs
