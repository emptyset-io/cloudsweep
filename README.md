# Cloud Sweep: AWS Resource Scanner & Unused Resource Identifier

Cloud Sweep is a Python-based utility designed to scan AWS resources across multiple AWS Organizations, Accounts, and Regions. It helps identify unused resources, providing valuable insights to optimize your AWS environment and reduce costs.

## Key Features

- **Scan Multiple AWS Organizations & Regions**: Seamlessly scan multiple AWS organizations and all regions within those organizations to identify unused resources.
- **Identify Unused Resources**: Detect unused AWS resources and generate detailed reports with explanations on why they are considered unused.
- **Optimize AWS Resource Usage**: Take action on unused resources to reduce costs and streamline your AWS environment.
- **Cost Showback**: Gives a breakdown of `hourly`, `daily`, `monthly`, `yearly` and `lifetime` cost for supported unused resources.
### AWS Cost Estimator

The **AWS Cost Estimator** calculates the cost of resources based on live AWS pricing. 

#### Currently Supported Services:
- **EC2**: Elastic Compute Cloud instances (e.g., `t2.micro`, `m5.large`).
- **EBS**: Elastic Block Store volumes and snapshots.
- **Elastic IPs**: Static IP addresses.
## Future Enhancements

- **Integrate with Atlassian Tools (Jira/Confluence)**: Automatically generate workstreams for flagged resources in Jira and Confluence.
- **Integrate with Slack & PagerDuty**: Set up alerts for newly discovered unused resources.
- **Implement Cost Showback**: Add additional services to cost estimation
- **Develop Real UI**: The current report ui is just a WIP with some basic features. 

## Example Report

You can view an example of the generated report [here](https://missionctlio.github.io/cloudsweep/examples/random_scan_report.html). The report contains metadata on each resource, including why it was flagged as unused.
The report data is randomized seed data, actual metadata in the Details column generally contains all associated metadata returned from boto3 about the resource, which is not accurately conveyed in the example report.

## Prerequisites
### AWS Setup
- **AWS Credentials**: Ensure you have AWS credentials configured on your system. You can use `aws configure` or set up the `~/.aws/credentials` file.
- **Organization Role** (`--organization-role`): This IAM role is required to query organization-level resources (e.g., account details) and must be created in the organization’s account.
  - Your profile must have permissions to assume this role, and it should have the ability to assume the `runner_role` in each account.
- **Runner Role** (`--runner-role`): This IAM role must exist in each account associated with your AWS Organization and have read-only access to AWS resources (e.g., EC2, S3).
  - The `runner_role` must be assumable by the `organization_role`.

### Permissions Setup
Both the `organization_role` and `runner_role` must have appropriate permissions for resource scanning across all accounts and regions within your AWS Organization.

#### Example organization_role Permissions

```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Resource": [
                "arn:aws:iam::<account1_id>:role/<runner_role>",
                "arn:aws:iam::<account2_id>:role/<runner_role>",
                "arn:aws:iam::<account3_id>:role/<runner_role>",
            ],
            "Sid": ""
        },
        {
            "Action": [
                "ses:SendRawEmail",
                "ses:SendEmail",
                "ec2:DescribeRegions",
                "organizations:ListPolicies",
                "organizations:ListOrganizationalUnitsForParent",
                "organizations:ListChildren",
                "organizations:ListAccounts",
                "organizations:DescribePolicy",
                "organizations:DescribeOrganizationalUnit",
                "organizations:DescribeAccount"
            ],
            "Effect": "Allow",
            "Resource": "*",
            "Sid": ""
        }
    ]
}
```

#### Example runner_role Permissions
The runner_role requires the canned ReadOnlyAccess permission policy associated to it with a trust relationship from the `organization_role`

Example Trust Relationship Policy
```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "",
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::<organization_account_id>:role/<organization_role>"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
```

## Installation & Setup

### 1. Clone the Repository

```
git clone https://github.com/missionctlio/cloudsweeper.git
cd cloudsweep
```

### 2. Install Dependencies

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure AWS Credentials

Make sure your AWS credentials are configured for the profiles you intend to scan.

## How to Use Cloud Sweep

Cloud Sweep scans AWS resources across multiple profiles and regions. Use the command-line arguments to customize your scan settings.

### Command-Line Arguments

- `--organization-role`: Specify the IAM role for querying the AWS Organization.
- `--runner-role`: Specify the IAM role for scanning accounts within the AWS Organization.
- `--list-scanners`: List available scanners without performing a scan.
- `--all-scanners`: Run all available scanners.
- `--scanners`: A comma-separated list of scanners to run (e.g., `ec2,elb,iam`).
- `--regions`: Specify AWS regions to scan (e.g., `us-west-2,us-east-1`).
- `--all-regions`: Scan all AWS regions.
- `--max-workers`: Number of concurrent threads to use for scanning. Defaults to one less than the number of CPUs.

## Environment Variables

The AWS Scanner CLI can be configured using environment variables. This allows you to set default values for the command-line arguments, making it easier to run the tool without having to specify all the arguments each time.

### Supported Environment Variables

Below are the environment variables you can use to configure the AWS Scanner CLI:

| **Environment Variable**       | **Description**                                                       | **Default Value**       |
|---------------------------------|-----------------------------------------------------------------------|-------------------------|
| `CS_ORGANIZATION_ROLE`         | The IAM Role Name used to query the organization.                    | (No default, must be set) |
| `CS_RUNNER_ROLE`               | The IAM Role Name for scanning organization accounts.                | (No default, must be set) |
| `CS_SCANNERS`                  | A comma-separated list of scanners to use (e.g., `scanner1,scanner2`). If set to `"all"`, all available scanners are used. | `all`                   |
| `CS_REGIONS`                   | A comma-separated list of AWS regions to scan (e.g., `us-east-1,us-west-2`). If set to `"all"`, all regions are used. | `all`                   |
| `CS_MAX_WORKERS`               | The maximum number of workers to use for scanning (default: one less than the number of CPUs). | (System default, typically `os.cpu_count() - 1`) |
| `CS_DAYS_THRESHOLD`            | The number of days to look back at resource metrics and history to determine if something is unused. This is used to identify unused resources. | `90`                    |

### Example `.env` File

To simplify configuration, you can create a `.env` file in your project directory. Below is an example `.env` file that sets the necessary environment variables:

```
CS_ORGANIZATION_ROLE=my-organization-role
CS_RUNNER_ROLE=my-runner-role
CS_SCANNERS=  # If left empty, defaults to 'all' (i.e., use all scanners)
CS_REGIONS=  # If left empty, defaults to 'all' (i.e., use all regions)
CS_MAX_WORKERS=4
CS_DAYS_THRESHOLD=90  # Default value is 90 days
```

### Example Commands

#### 1. List Available Scanners

```
python main.py --list-scanners
```

#### 2. Scan All Available Scanners

```
python main.py --all-scanners --organization-role <organization_role> --runner-role <runner_role>
```

#### 3. Scan Specific Scanners (e.g., EC2, IAM)

```
python main.py --scanners ec2,iam --organization-role <organization_role> --runner-role <runner_role>
```

#### 4. Scan All Regions

```
python main.py --all-regions --profile <profile> --organization-role <organization_role> --runner-role <runner_role>
```

#### 5. Scan with Custom Number of Workers

```
python main.py --max-workers 10 --organization-role <organization_role> --runner-role <runner_role>
```

## How It Works

- **Roles** The boto3 session assumes role into an `organization_role` and from there lists accounts in the organization to scan.  The boto3 session then assumes role into each of the sub accounts via the `scanner_role`, returninig a list of used regions for each account to be passed off to the scanner.
- **Regions**: If no regions are specified, Cloud Sweep defaults to scanning all AWS regions.
- **Scanners**: You can specify which scanners to run, or use `--all-scanners` to run them all.
- **Max Workers**: Determines how many concurrent scans are performed. Increasing workers speeds up the process.

## Output

Cloud Sweep generates an HTML report with resource scan results, listing resource types, IDs, and additional metadata. Results can also be exported as CSV files from within the HTML report UI.

## Current Scanners

Cloud Sweep includes several scanners to identify unused AWS resources, including:

1. **CloudFormation** (`cloudformation`): Scans for unused CloudFormation stacks.
2. **DynamoDB** (`dynamodb`): Scans for unused DynamoDB tables.
3. **EBS Snapshots** (`ebs-snapshots`): Scans for unused EBS snapshots.
4. **EBS Volumes** (`ebs-volumes`): Scans for unused EBS volumes.
5. **EC2 Instances** (`ec2`): Scans for unused EC2 instances.
6. **Elastic IPs** (`elastic-ips`): Scans for unused Elastic IPs.
7. **IAM Roles** (`iam-roles`): Scans for unused IAM roles.
8. **IAM Users** (`iam-users`): Scans for unused IAM users.
9. **Load Balancers** (`load-balancers`): Scans for unused load balancers.
10. **RDS Instances** (`rds`): Scans for unused RDS instances.
11. **S3 Buckets** (`s3`): Scans for unused S3 buckets.
12. **Security Groups** (`security-groups`): Scans for unused security groups.
13. **VPCs** (`vpcs`): Scans for unused VPCs.

## Contributing

We welcome contributions! Fork the repository, make changes, and submit a pull request. Ensure your code follows our coding standards and includes appropriate tests.

## License

This project is licensed under the **Mozilla Public License 2.0 (MPL-2.0)**. For more details, refer to the [license page](https://www.mozilla.org/MPL/2.0/).

### Commercial License

For full proprietary use, premium features, or additional support, contact us at **[support@missionctl.io](mailto:support@missionctl.io)** for commercial licensing options.

## Author

**Chris Molle** – Creator and Maintainer of Cloud Sweep.
