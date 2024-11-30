import os
import multiprocessing
from utils.logger import get_logger


logger = get_logger(__name__)

# Confluence configuration
BASE_URL = os.getenv('CONFLUENCE_BASE_URL')  # Your Confluence instance URL (e.g., https://yourcompany.atlassian.net/wiki)
SPACE_KEY = os.getenv('CONFLUENCE_SPACE_KEY')  # The space key in Confluence
PAGE_ID = os.getenv('CONFLUENCE_PAGE_ID')  # Page ID where reports will be uploaded
USERNAME = os.getenv('CONFLUENCE_USERNAME')  # Your Confluence username (email)
API_TOKEN = os.getenv('CONFLUENCE_API_TOKEN')  # Your Confluence API token

DAYS_THRESHOLD = os.getenv('DAYS_THRESHOLD', 90)

RESOURCE_SCANNER_MAP = {
    "EC2 Instances": "ec2",  # Refers to get_unused_ec2_instances in src/scanner/resources/ec2.py
    "Load Balancers": "elb",  # Refers to get_unused_load_balancers in src/scanner/resources/elb.py
    "Elastic IPs": "eip",  # Refers to get_unused_elastic_ips in src/scanner/resources/eip.py
    "Security Groups": "sgs",  # Refers to get_unused_security_groups in src/scanner/resources/sgs.py
    "IAM Roles": "iam",  # Refers to get_unused_iam_roles in src/scanner/resources/iam.py
    "VPCs": "vpc",  # Refers to get_unused_vpcs in src/scanner/resources/vpc.py
    "EBS Volumes": "ebs_volumes",  # Refers to get_unused_ebs_volumes in src/scanner/resources/ebs.py
    "EBS Snapshots": "ebs_snapshots",  # Refers to get_unused_ebs_snapshots in src/scanner/resources/ebs.py
    "S3 Buckets": "s3",  # Refers to get_unused_s3_buckets in src/scanner/resources/s3.py
    "Lambda Functions": "lambdas",  # Refers to get_unused_lambda_functions in src/scanner/resources/lambdas.py
    "CloudFormation Stacks": "cloudformation",  # Refers to get_unused_cloudformation_stacks in src/scanner/resources/cloudformation.py
    "RDS Instances": "rds",  # Refers to get_unused_rds_instances in src/scanner/resources/rds.py
    "DynamoDB": "dynamodb",  # Refers to get_unused_rds_instances in src/scanner/resources/dynamodb.py
}