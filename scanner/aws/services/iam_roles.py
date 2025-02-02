from datetime import datetime, timezone
from utils.logger import get_logger
from config.config import DAYS_THRESHOLD
from scanner.resource_scanner_registry import ResourceScannerRegistry
from scanner.aws.utils.scanner_helper import calculate_and_format_age_in_time_units

logger = get_logger(__name__)

class IAMRoleScanner(ResourceScannerRegistry):
    """
    Scanner for identifying unused IAM roles.
    """
    argument_name = "iam-roles"
    label = "IAM Roles"

    def __init__(self):
        super().__init__(name=__name__, argument_name=self.argument_name, label=self.label)

    def scan(self, session, *args, **kwargs):
        """
        Retrieve and identify unused IAM roles based on usage and policy criteria.

        :param session: Boto3 session object for AWS API calls.
        :return: List of unused IAM roles with details.
        """
        logger.debug("Starting scan for unused IAM Roles...")
        try:
            iam_client = session.get_client("iam")
            roles = iam_client.list_roles().get("Roles", [])
            unused_roles = []
            current_time = datetime.now(timezone.utc)

            for role in roles:
                role_name = role["RoleName"]
                role_arn = role["Arn"]
                logger.debug(f"Checking role: {role_name} (ARN: {role_arn})")

                # Skip service or reserved roles
                if self._is_reserved_role(role_arn):
                    logger.debug(f"Skipping reserved role: {role_name}")
                    continue

                # Analyze role details
                last_used, last_used_time = self._get_role_last_used(iam_client, role_name, current_time)

                # Calculate formatted age string
                age_string = (
                    calculate_and_format_age_in_time_units(current_time, last_used_time)
                    if last_used_time
                    else "Never used"
                )

                attached_policies, inline_policies, instance_profiles = self._get_role_policies(iam_client, role_name)

                # Determine reasons for unused status
                reasons = self._determine_unused_reasons(last_used_time, attached_policies, inline_policies, instance_profiles, age_string)

                if reasons:
                    unused_roles.append({
                        "ResourceName": role_name,
                        "ResourceId": role_arn,
                        "LastUsed": age_string,
                        "InstanceProfiles": len(instance_profiles),
                        "PoliciesAttached": len(attached_policies) + len(inline_policies),
                        "Reason": "\n".join(reasons),
                    })
                    logger.debug(f"Unused role identified: {role_name} - Reasons: {reasons}")

            logger.info(f"Found {len(unused_roles)} unused IAM Roles.")
            return unused_roles

        except Exception as e:
            logger.error(f"Error during IAM role scan: {e}")
            return []

    def _is_reserved_role(self, role_arn):
        """Check if the role is reserved (service or AWS reserved)."""
        return "service-role" in role_arn or "aws-reserved" in role_arn

    def _get_role_last_used(self, iam_client, role_name, current_time):
        """Retrieve the last used time and calculate time since last used."""
        role_details = iam_client.get_role(RoleName=role_name)["Role"]
        last_used = role_details.get("RoleLastUsed", {}).get("LastUsedDate")
        return last_used, last_used if last_used else None

    def _get_role_policies(self, iam_client, role_name):
        """Retrieve the attached policies, inline policies, and instance profiles for the role."""
        attached_policies = iam_client.list_attached_role_policies(RoleName=role_name).get("AttachedPolicies", [])
        inline_policies = iam_client.list_role_policies(RoleName=role_name).get("PolicyNames", [])
        instance_profiles = iam_client.list_instance_profiles_for_role(RoleName=role_name).get("InstanceProfiles", [])
        return attached_policies, inline_policies, instance_profiles

    def _determine_unused_reasons(self, last_used_time, attached_policies, inline_policies, instance_profiles, age_string):
        """Determine the reasons the role is considered unused."""
        reasons = []
        if not last_used_time:
            reasons.append("Role has never been used.")
        elif (datetime.now(timezone.utc) - last_used_time).days > DAYS_THRESHOLD:
            reasons.append(f"Role has not been used for {age_string}.")
        if not attached_policies and not inline_policies and not instance_profiles:
            reasons.append("No attached policies or instance profiles.")
        return reasons
