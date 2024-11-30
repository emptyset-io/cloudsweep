from datetime import datetime, timezone
from utils.logger import get_logger
from config.config import DAYS_THRESHOLD
from scanner.resource_scanner_registry import ResourceScannerRegistry

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
                last_login_days = self._get_last_login_days(user, current_time)
                key_last_used_days = self._get_latest_key_usage_days(iam_client, user_name, current_time)

                # Determine reasons for unused status
                reasons = self._determine_unused_reasons(last_login_days, key_last_used_days)

                if reasons:
                    unused_users.append({
                        "ResourceName": user_name,
                        "ResourceId": user_arn,
                        "LastLogin": self._format_last_used(last_login_days),
                        "LastKeyUsage": self._format_last_used(key_last_used_days),
                        "AccountId": session.account_id,
                        "Reason": "\n".join(reasons),
                    })
                    logger.debug(f"Unused user identified: {user_name} - Reasons: {reasons}")

            logger.info(f"Found {len(unused_users)} unused IAM Users.")
            return unused_users

        except Exception as e:
            logger.error(f"Error during IAM user scan: {e}")
            return []

    def _get_last_login_days(self, user, current_time):
        """Retrieve the last login days for a user."""
        last_login = user.get("PasswordLastUsed")
        return (current_time - last_login).days if last_login else -1

    def _get_latest_key_usage_days(self, iam_client, user_name, current_time):
        """Retrieve the latest key usage days for a user."""
        try:
            access_keys = iam_client.list_access_keys(UserName=user_name).get("AccessKeyMetadata", [])
            latest_usage_days = -1
            for key in access_keys:
                key_id = key["AccessKeyId"]
                key_last_used = iam_client.get_access_key_last_used(AccessKeyId=key_id).get("AccessKeyLastUsed", {}).get("LastUsedDate")
                if key_last_used:
                    days_since_last_use = (current_time - key_last_used).days
                    latest_usage_days = max(latest_usage_days, days_since_last_use)
            return latest_usage_days
        except Exception as e:
            logger.error(f"Error checking key usage: {e}")
            return -1

    def _determine_unused_reasons(self, last_login_days, key_last_used_days):
        """Determine the reasons the user is considered unused."""
        reasons = []
        if last_login_days == -1 and key_last_used_days == -1:
            reasons.append("User has never logged in or used access keys.")
        else:
            if last_login_days >= DAYS_THRESHOLD:
                reasons.append(f"UI login last used {last_login_days} days ago.")
            if key_last_used_days >= DAYS_THRESHOLD:
                reasons.append(f"Access keys last used {key_last_used_days} days ago.")
        return reasons

    def _format_last_used(self, last_used_days):
        """Format the last used time into a readable string."""
        return "Never" if last_used_days == -1 else f"{last_used_days} days ago"
