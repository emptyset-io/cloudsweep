from datetime import datetime, timezone
from utils.logger import get_logger
from config.config import DAYS_THRESHOLD
from scanner.resource_scanner_registry import ResourceScannerRegistry
from scanner.aws.utils.scanner_helper import determine_metric_time_window, fetch_metric, determine_unused_reason

logger = get_logger(__name__)

class DynamoDBScanner(ResourceScannerRegistry):
    """
    Scanner for DynamoDB tables.
    """
    argument_name = "dynamodb"
    label = "DynamoDB Tables"
    result_keys = {"Name": "TableName", "ResourceId": "TableName"}

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

                # Determine the start time for metrics
                start_time = determine_metric_time_window(creation_time, current_time, DAYS_THRESHOLD)

                # Check DynamoDB table usage
                table_usage = self.check_dynamodb_usage(cloudwatch_client, table_name, start_time, current_time)
                reason = table_usage.get("reason")

                if reason:
                    unused_tables.append({
                        "ResourceName": table_name,
                        "ResourceId": table_name,
                        "CreationDateTime": creation_time,
                        "ItemCount": table_info.get("ItemCount", 0),
                        "TableSizeBytes": table_info.get("TableSizeBytes", 0),
                        "AccountId": session.account_id,
                        "Reason": reason,
                    })
                    logger.debug(f"DynamoDB table {table_name} is unused or underutilized: {reason}")

            logger.info(f"Found {len(unused_tables)} unused DynamoDB tables.")
            return unused_tables
        except Exception as e:
            logger.error(f"Error retrieving DynamoDB tables: {e}")
            return []

    def check_dynamodb_usage(self, cloudwatch_client, table_name, start_time, end_time):
        """Check the DynamoDB table's read/write capacity and throttled events metrics."""
        
        # Fetch metrics using the updated fetch_metric function
        metrics = {
            "read_capacity": fetch_metric(
                cloudwatch_client, "AWS/DynamoDB", table_name, "TableName", "ConsumedReadCapacityUnits", "Sum", start_time, end_time
            ),
            "write_capacity": fetch_metric(
                cloudwatch_client, "AWS/DynamoDB", table_name, "TableName", "ConsumedWriteCapacityUnits", "Sum", start_time, end_time
            ),
            "throttled_events": fetch_metric(
                cloudwatch_client, "AWS/DynamoDB", table_name, "TableName", "ProvisionedThroughputExceededEvents", "Sum", start_time, end_time
            ),
        }

        # Process metrics
        read_capacity_total = sum(metrics["read_capacity"])  # Summing the values from the list
        write_capacity_total = sum(metrics["write_capacity"])  # Summing the values from the list
        throttled_events_total = sum(metrics["throttled_events"])  # Summing the values from the list

        unused_conditions = [
            (lambda m: (read_capacity_total == 0 and write_capacity_total == 0, "No read or write activity.")),
            (lambda m: (throttled_events_total > 0, f"Provisioned throughput exceeded events: {throttled_events_total}.")),
        ]

        reason = determine_unused_reason(metrics, unused_conditions)
        if reason:
            metrics["reason"] = reason
        
        # Return metrics including the reason
        return metrics
