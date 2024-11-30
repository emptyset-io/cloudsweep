import boto3
import json
from utils.logger import get_logger
import locale

# Set locale for currency formatting
locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
logger = get_logger(__name__)

class CostEstimator:
    """
    AWS Cost Estimator that calculates the cost of resources based on live AWS pricing.
    """

    def __init__(self):
        self.pricing_client = boto3.client('pricing', region_name="us-east-1")
        self.price_cache = {}

    def _get_aws_price(self, service_code, price_filters):
        """
        Retrieves the price for a specific AWS service and attributes from AWS Pricing.
        """
        cache_key = (service_code, frozenset(price_filters.items()))
        if cache_key in self.price_cache:
            return self.price_cache[cache_key]

        try:
            filters = [{"Type": "TERM_MATCH", "Field": key, "Value": value} for key, value in price_filters.items()]
            response = self.pricing_client.get_products(ServiceCode=service_code, Filters=filters)
            price_list = response.get("PriceList", [])

            if not price_list:
                logger.warning(f"No pricing information found for {service_code} with filters {price_filters}.")
                return None

            # Parse JSON response
            pricing_data = json.loads(price_list[0])
            on_demand_terms = pricing_data["terms"]["OnDemand"]
            term_key = list(on_demand_terms.keys())[0]
            price_dimensions = on_demand_terms[term_key]["priceDimensions"]
            price_key = list(price_dimensions.keys())[0]
            price_per_unit = float(price_dimensions[price_key]["pricePerUnit"]["USD"])

            self.price_cache[cache_key] = price_per_unit
            return price_per_unit

        except Exception as error:
            logger.error(f"Error retrieving pricing for {service_code}: {error}")
            return None

    def calculate_cost(self, resource_type, resource_size=None, hours_running=0):
        """
        Calculates the cost for a given resource type, size, and running duration.

        :param resource_type: AWS resource type (e.g., 'EBS', 'EC2', 'RDS').
        :param resource_size: Size of the resource (e.g., GiB for storage, instance type for compute).
        :param hours_running: Duration in hours the resource is running.
        :return: A dictionary with cost estimates for different time units.
        """
        # Map resource types to AWS service codes
        service_code_map = {
            "EBS": "AmazonEC2",
            "EC2": "AmazonEC2",
            "EBS-Snapshots": "AmazonEC2",
            "RDS": "AmazonRDS",
            "DynamoDB": "AmazonDynamoDB",
            "EIP": "AmazonEC2",
            "LoadBalancer": "ElasticLoadBalancing",
        }

        # Attribute filters for pricing queries
        price_filter_map = {
            "EBS": {"productFamily": "Storage", "volumeType": "General Purpose"},
            "EC2": {"productFamily": "Compute Instance", "instanceType": resource_size},
            "EBS-Snapshots": {"productFamily": "Storage Snapshot"},
            "RDS": {"productFamily": "Database Instance", "instanceType": resource_size},
            "DynamoDB": {"productFamily": "Non-relational Database"},
            "EIP": {"productFamily": "IP Address"},
            "LoadBalancer": {"productFamily": "Load Balancer"},
        }

        service_code = service_code_map.get(resource_type)
        if not service_code:
            raise ValueError(f"Unsupported resource type: {resource_type}")

        price_filters = price_filter_map.get(resource_type)
        if not price_filters:
            raise ValueError(f"Attribute filters not defined for resource type: {resource_type}")

        # Fetch price per hour from AWS Pricing API
        price_per_hour = self._get_aws_price(service_code, price_filters)
        if price_per_hour is None:
            logger.warning(f"Could not calculate cost for {resource_type} of size {resource_size}.")
            return None

        # Calculate costs
        cost_per_hour = price_per_hour
        cost_per_day = cost_per_hour * 24
        cost_per_month = cost_per_day * 30
        cost_per_year = cost_per_day * 365
        lifetime_cost = cost_per_hour * hours_running  # Lifetime cost

        # Format costs in currency
        def format_currency(amount):
            return f"${amount:,.2f}"

        return {
            "hourly": format_currency(cost_per_hour),
            "daily": format_currency(cost_per_day),
            "monthly": format_currency(cost_per_month),
            "yearly": format_currency(cost_per_year),
            "lifetime": format_currency(lifetime_cost),
        }
