# Cloud Sweep: AWS Resource Scanner & Unused Resource Identifier

Cloud Sweep is a Python-based utility designed to scan AWS resources across multiple AWS Organizations, Accounts, and Regions. It helps identify unused resources, providing valuable insights to optimize your AWS environment and reduce costs.

## Key Features

- **Scan Multiple AWS Organizations & Regions**: Seamlessly scan multiple AWS organizations and all regions within those organizations to identify unused resources.
- **Identify Unused Resources**: Detect unused AWS resources and generate detailed reports with explanations on why they are considered unused.
- **Optimize AWS Resource Usage**: Take action on unused resources to reduce costs and streamline your AWS environment.

## Future Enhancements

- **Integrate with Atlassian Tools (Jira/Confluence)**: Automatically generate workstreams for flagged resources in Jira and Confluence.
- **Integrate with Slack & PagerDuty**: Set up alerts for newly discovered unused resources.
- **Implement Cost Showback**: Display cost breakdowns of unused resources with customizable filtering options.
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
- `--profile`: AWS profile to use. Defaults to the profile specified in `~/.aws/credentials`.
- `--list-scanners`: List available scanners without performing a scan.
- `--all-scanners`: Run all available scanners.
- `--scanners`: A comma-separated list of scanners to run (e.g., `ec2,elb,iam`).
- `--regions`: Specify AWS regions to scan (e.g., `us-west-2,us-east-1`).
- `--all-regions`: Scan all AWS regions.
- `--max-workers`: Number of concurrent threads to use for scanning. Defaults to one less than the number of CPUs.

### Environment Variables

Set the following environment variables to override the command-line arguments:

- **`AWS_SCANNER_ORGANIZATION_ROLE`**: Overrides `--organization-role`.
- **`AWS_SCANNER_RUNNER_ROLE`**: Overrides `--runner-role`.

### Example Commands

#### 1. List Available Scanners

```
python main.py --list-scanners
```

#### 2. Scan with Specific Profile and Regions

```
python main.py --profile profile1 --regions us-west-2,us-east-1 --organization-role <organization_role> --runner-role <runner_role>
```

#### 3. Scan All Available Scanners

```
python main.py --all-scanners --organization-role <organization_role> --runner-role <runner_role> --profile <profile>
```

#### 4. Scan Specific Scanners (e.g., EC2, IAM)

```
python main.py --scanners ec2,iam --organization-role <organization_role> --runner-role <runner_role> --profile <profile>
```

#### 5. Scan All Regions

```
python main.py --all-regions --profile <profile> --organization-role <organization_role> --runner-role <runner_role>
```

#### 6. Scan with Custom Number of Workers

```
python main.py --max-workers 10 --organization-role <organization_role> --runner-role <runner_role> --profile <profile>
```

## How It Works

- **Profile**: The profile is used to create the inital boto3 session. The default profile is used if none is specified. The boto3 session assumes role into an `organization_role` and from there lists accounts in the organization to scan.  The boto3 session then assumes role into each of the sub accounts via the `scanner_role`, returninig a list of used regions for each account to be passed off to the scanner.
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
