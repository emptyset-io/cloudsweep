# from datetime import datetime, timedelta, timezone
# from utils.logger import get_logger
# from config.config import DAYS_THRESHOLD
# from scanner.resource_scanner_registry import ResourceScannerRegistry
# from scanner.aws.utils.scanner_helper import fetch_metric
# from scanner.aws.cost_estimator import CostEstimator
# import numpy as np

# logger = get_logger(__name__)

# class EksScanner(ResourceScannerRegistry):
#     """
#     Scanner for EKS Clusters and their associated resources.
#     """
#     argument_name = "eks"
#     label = "EKS Clusters"

#     def __init__(self):
#         super().__init__(name=__name__, argument_name=self.argument_name, label=self.label)
#         self.cost_estimator = CostEstimator()  # Initialize Cost Estimator

#     def scan(self, session, *args, **kwargs):
#         """Retrieve EKS clusters and flag unused or underutilized resources."""
#         logger.debug("Retrieving EKS clusters...")
#         try:
#             eks_client = session.get_client("eks")
#             ec2_client = session.get_client("ec2")
#             clusters = eks_client.list_clusters()["clusters"]
#             unused_clusters = []

#             for cluster_name in clusters:
#                 logger.debug(f"Processing EKS cluster {cluster_name}...")
#                 cluster_info = eks_client.describe_cluster(name=cluster_name)["cluster"]
#                 cluster_arn = cluster_info["arn"]
#                 cluster_status = cluster_info["status"]
#                 creation_time = cluster_info["createdAt"]

#                 # Skip inactive clusters
#                 if cluster_status != "ACTIVE":
#                     logger.info(f"Cluster {cluster_name} is not active (status: {cluster_status}). Skipping.")
#                     continue

#                 # Determine if the cluster is unused
#                 days_since_creation = (datetime.now(timezone.utc) - creation_time).days
#                 start_time = creation_time if days_since_creation < DAYS_THRESHOLD else datetime.now(timezone.utc) - timedelta(days=DAYS_THRESHOLD)

#                 # Analyze resource usage
#                 metrics = self._analyze_cluster_usage(session, cluster_name, start_time)
#                 reasons = metrics.get("reasons", [])
#                 total_cost = self._calculate_combined_costs(session, cluster_arn, metrics)

#                 if reasons:
#                     unused_clusters.append({
#                         "ClusterName": cluster_name,
#                         "Reasons": reasons,
#                         "Cost": total_cost,
#                         "CreationTime": creation_time,
#                         "Status": cluster_status,
#                     })
#                     logger.info(f"EKS cluster {cluster_name} is underutilized: {', '.join(reasons)}")

#             logger.info(f"Found {len(unused_clusters)} unused or underutilized EKS clusters.")
#             return unused_clusters
#         except Exception as e:
#             logger.exception(f"Error retrieving EKS clusters: {e}")
#             return []

#     def _analyze_cluster_usage(self, session, cluster_name, start_time):
#         """Analyze usage of EKS cluster and its resources."""
#         cloudwatch_client = session.get_client("cloudwatch")
#         reasons = []

#         # Fetch cluster-level CPU and memory usage
#         cpu_usage = fetch_metric(
#             cloudwatch_client, "AWS/EKS", cluster_name, "ClusterName", "CPUUtilization", "Average", start_time, datetime.now(timezone.utc)
#         )
#         memory_usage = fetch_metric(
#             cloudwatch_client, "AWS/EKS", cluster_name, "ClusterName", "MemoryUtilization", "Average", start_time, datetime.now(timezone.utc)
#         )

#         if cpu_usage and np.mean(cpu_usage) < 2:  # Example threshold for low CPU usage
#             reasons.append(f"Low cluster CPU usage: {np.mean(cpu_usage):.2f}% average over the last {DAYS_THRESHOLD} days")

#         if memory_usage and np.mean(memory_usage) < 20:  # Example threshold for low memory usage
#             reasons.append(f"Low cluster memory usage: {np.mean(memory_usage):.2f}% average over the last {DAYS_THRESHOLD} days")

#         # Fetch usage for associated EC2 instances
#         instance_ids = self._get_cluster_instances(session, cluster_name)
#         ec2_usage_reasons = self._analyze_ec2_instances(session, instance_ids, start_time)
#         reasons.extend(ec2_usage_reasons)

#         return {"reasons": reasons}

#     def _get_cluster_instances(self, session, cluster_name):
#         """Retrieve EC2 instances associated with the EKS cluster."""
#         ec2_client = session.get_client("ec2")
#         instances = ec2_client.describe_instances(Filters=[{"Name": "tag:eks:cluster-name", "Values": [cluster_name]}])
#         return [instance["InstanceId"] for reservation in instances["Reservations"] for instance in reservation["Instances"]]

#     def _analyze_ec2_instances(self, session, instance_ids, start_time):
#         """Analyze EC2 instances associated with the cluster for underutilization."""
#         cloudwatch_client = session.get_client("cloudwatch")
#         reasons = []

#         for instance_id in instance_ids:
#             cpu_usage = fetch_metric(
#                 cloudwatch_client, "AWS/EC2", instance_id, "InstanceId", "CPUUtilization", "Average", start_time, datetime.now(timezone.utc)
#             )
#             network_in = fetch_metric(
#                 cloudwatch_client, "AWS/EC2", instance_id, "InstanceId", "NetworkPacketsIn", "Sum", start_time, datetime.now(timezone.utc)
#             )
#             network_out = fetch_metric(
#                 cloudwatch_client, "AWS/EC2", instance_id, "InstanceId", "NetworkPacketsOut", "Sum", start_time, datetime.now(timezone.utc)
#             )

#             if cpu_usage and np.mean(cpu_usage) < 5:  # Example threshold for low CPU usage
#                 reasons.append(f"Low CPU usage on instance {instance_id}: {np.mean(cpu_usage):.2f}% average")

#             if (network_in and sum(network_in) < 1_000_000) and (network_out and sum(network_out) < 1_000_000):
#                 reasons.append(f"Low network traffic on instance {instance_id}: less than 1 million packets")

#         return reasons

#     def _calculate_combined_costs(self, session, cluster_arn, metrics):
#         """Calculate the costs of the cluster, associated EC2 instances, and storage."""
#         total_costs = {
#             "hourly": 0,
#             "daily": 0,
#             "monthly": 0,
#             "yearly": 0,
#         }

#         # # Calculate cluster cost
#         cluster_cost = self.cost_estimator.calculate_cost("EKS Clusters", resource_arn=cluster_arn)
#         for cost_type in total_costs:
#             total_costs[cost_type] += cluster_cost.get(cost_type, 0)

#         # Calculate EC2 instance costs
#         instance_ids = self._get_cluster_instances(session, cluster_arn.split("/")[-1])
#         for instance_id in instance_ids:
#             instance_cost = self.cost_estimator.calculate_cost("EC2 Instances", resource_id=instance_id)
#             for cost_type in total_costs:
#                 total_costs[cost_type] += instance_cost.get(cost_type, 0)

#         # Calculate EBS volume costs
#         ec2_client = session.get_client("ec2")
#         for instance_id in instance_ids:
#             volumes = ec2_client.describe_volumes(Filters=[{"Name": "attachment.instance-id", "Values": [instance_id]}])["Volumes"]
#             for volume in volumes:
#                 volume_cost = self.cost_estimator.calculate_cost("EBS Volumes", resource_size=volume["Size"])
#                 for cost_type in total_costs:
#                     total_costs[cost_type] += volume_cost.get(cost_type, 0)

#         logger.debug(f"Total costs for cluster {cluster_arn}: {total_costs}")
#         return total_costs
