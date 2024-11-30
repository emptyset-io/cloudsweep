from datetime import timedelta, datetime

def determine_metric_time_window(resource_creation_time, current_time, days_threshold):
    """
    Determine the time window for metric collection based on the resource creation time and a threshold.

    :param resource_creation_time: The creation time of the resource.
    :param current_time: The current time.
    :param days_threshold: The threshold in days to determine the start of the window.
    :return: A datetime object for the metric collection start time.
    """
    return max(current_time - timedelta(days=days_threshold), resource_creation_time)


def fetch_metric(cloudwatch_client, namespace, resource_name, dimension_name, metric_name, stat, start_time, end_time):
    """
    Fetch CloudWatch metrics for a given resource and return a list of values instead of a single sum.

    :param cloudwatch_client: Boto3 CloudWatch client.
    :param namespace: AWS CloudWatch namespace (e.g., AWS/EC2, AWS/DynamoDB).
    :param resource_name: The name of the resource (e.g., InstanceId or TableName).
    :param dimension_name: The dimension name (e.g., 'InstanceId', 'TableName').
    :param metric_name: The name of the metric to query.
    :param stat: The statistic type (e.g., Sum, Average).
    :param start_time: The start time for the metric query.
    :param end_time: The end time for the metric query.
    :return: A list of metric values or an empty list if no data is available.
    """
    try:
        metric_data = cloudwatch_client.get_metric_data(
            MetricDataQueries=[{
                'Id': f'{metric_name.lower()}Query',
                'MetricStat': {
                    'Metric': {
                        'Namespace': namespace,
                        'MetricName': metric_name,
                        'Dimensions': [{'Name': dimension_name, 'Value': resource_name}],
                    },
                    'Period': 3600,  # 1-hour granularity, adjust as needed
                    'Stat': stat,
                },
                'ReturnData': True,
            }],
            StartTime=start_time,
            EndTime=end_time,
        )['MetricDataResults'][0]['Values']
        
        return metric_data  # Return the list of values (empty if no data available)
    
    except Exception as e:
        # Log error in your logger system
        print(f"Error fetching metric {metric_name} for {resource_name}: {e}")
        return []  # Return an empty list if there was an error

def determine_unused_reason(metric_values, unused_conditions):
    """
    Determine if a resource is unused based on its metric values and conditions.

    :param metric_values: A dictionary of metric values (e.g., CPU, network, etc.).
    :param unused_conditions: A list of conditions to evaluate for marking the resource as unused.
                              Each condition is a callable that returns a tuple (is_unused: bool, reason: str).
    :return: The reason for being unused if applicable, else None.
    """
    for condition in unused_conditions:
        is_unused, reason = condition(metric_values)
        if is_unused:
            return reason
    return None

def extract_tag_value(tags, key, default="Unnamed"):
    """
    Extract the value of a specific key from a list of tags.

    :param tags: A list of tags, where each tag is a dictionary with "Key" and "Value".
    :param key: The key to search for in the tags.
    :param default: The default value to return if the key is not found.
    :return: The value associated with the key, or the default value if the key is not found.
    """
    if not tags:
        return default

    for tag in tags:
        if tag["Key"] == key:
            return tag["Value"]
    return default


def calculate_and_format_age_in_time_units(current_time: datetime, creation_time: datetime) -> str:
    """Calculate and format the age of a resource in years, months, weeks, days, and hours."""
    delta = current_time - creation_time

    # Calculate years, months, weeks, days, hours
    years = delta.days // 365
    months = (delta.days % 365) // 30
    weeks = (delta.days % 365) // 7
    days = delta.days % 7
    hours = delta.seconds // 3600

    # Build the reason string
    reason_parts = []
    
    if years > 0:
        reason_parts.append(f"{years} year{'s' if years > 1 else ''}")
    if months > 0:
        reason_parts.append(f"{months} month{'s' if months > 1 else ''}")
    if weeks > 0:
        reason_parts.append(f"{weeks} week{'s' if weeks > 1 else ''}")
    if days > 0:
        reason_parts.append(f"{days} day{'s' if days > 1 else ''}")
    if hours > 0:
        reason_parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
    
    # Join all parts into the reason string
    reason_string = ", ".join(reason_parts) if reason_parts else "Less than an hour old"
    
    return reason_string