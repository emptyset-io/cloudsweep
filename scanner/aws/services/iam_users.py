from datetime import datetime, timezone
from utils.logger import get_logger
from config.config import DAYS_THRESHOLD
from scanner.resource_scanner_registry import ResourceScannerRegistry
from scanner.aws.utils.scanner_helper import calculate_and_format_age_in_time_units

logger = get_logger(__name__)

class IAMUserScanner(ResourceScannerRegistry):
    """
    Scanner for identifying unused IAM users.
    """
    argument_name = "iam-users"
    label = "IAM Users"

    def __init__(self):
        super().__init__(name=__name__, argument_name=self.argument_name, label=self.label)

    def scan(self, session, *args, **kwargs):
        """
        Retrieve and identify unused IAM users based on UI or key activity within the defined threshold.

        :param session: Boto3 session object for AWS API calls.
        :return: List of unused IAM users with details.
        """
        logger.debug("Starting scan for unused IAM Users...")
        try:
            iam_client = session.get_client("iam")
            users = iam_client.list_users().get("Users", [])
            unused_users = []
            current_time = datetime.now(timezone.utc)

            for user in users:
                user_name = user["UserName"]
                user_arn = user["Arn"]
                logger.debug(f"Checking user: {user_name} (ARN: {user_arn})")

                # Check last UI activity and key activity
                last_login_time = user.get("PasswordLastUsed")
                key_last_used_time = self._get_latest_key_usage_time(iam_client, user_name)

                # Calculate formatted age strings
                last_login_age = (
                    calculate_and_format_age_in_time_units(current_time, last_login_time)
                    if last_login_time
                    else "Never used"
                )
                key_last_used_age = (
                    calculate_and_format_age_in_time_units(current_time, key_last_used_time)
                    if key_last_used_time
                    else "Never used"
                )

                # Determine reasons for unused status
                reasons = self._determine_unused_reasons(last_login_time, key_last_used_time, last_login_age, key_last_used_age)

                if reasons:
                    unused_users.append({
                        "ResourceName": user_name,
                        "ResourceId": user_arn,
                        "LastLogin": last_login_age,
                        "LastKeyUsage": key_last_used_age,
                        "Reason": "\n".join(reasons),
                    })
                    logger.debug(f"Unused user identified: {user_name} - Reasons: {reasons}")

            logger.info(f"Found {len(unused_users)} unused IAM Users.")
            return unused_users

        except Exception as e:
            logger.error(f"Error during IAM user scan: {e}")
            return []

    def _get_latest_key_usage_time(self, iam_client, user_name):
        """Retrieve the latest key usage time for a user."""
        try:
            access_keys = iam_client.list_access_keys(UserName=user_name).get("AccessKeyMetadata", [])
            latest_usage_time = None
            for key in access_keys:
                key_id = key["AccessKeyId"]
                key_last_used = iam_client.get_access_key_last_used(AccessKeyId=key_id).get("AccessKeyLastUsed", {}).get("LastUsedDate")
                if key_last_used and (latest_usage_time is None or key_last_used > latest_usage_time):
                    latest_usage_time = key_last_used
            return latest_usage_time
        except Exception as e:
            logger.error(f"Error checking key usage: {e}")
            return None

    def _determine_unused_reasons(self, last_login_time, key_last_used_time, last_login_age, key_last_used_age):
        """Determine the reasons the user is considered unused."""
        reasons = []
        if not last_login_time and not key_last_used_time:
            reasons.append("User has never logged in or used access keys.")
        else:
            if last_login_time and (datetime.now(timezone.utc) - last_login_time).days >= DAYS_THRESHOLD:
                reasons.append(f"UI login last used {last_login_age}.")
            if key_last_used_time and (datetime.now(timezone.utc) - key_last_used_time).days >= DAYS_THRESHOLD:
                reasons.append(f"Access keys last used {key_last_used_age}.")
        return reasons
