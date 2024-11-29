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

                # Check last UI activity
                last_login = user.get("PasswordLastUsed")
                last_login_days = (current_time - last_login).days if last_login else -1

                # Check last key activity
                access_keys = iam_client.list_access_keys(UserName=user_name).get("AccessKeyMetadata", [])
                key_last_used_days = self._get_latest_key_usage_days(iam_client, access_keys, current_time)

                # Determine reasons for unused status
                reasons = []
                if last_login_days == -1 and key_last_used_days == -1:
                    reasons.append("User has never logged in or used access keys.")
                else:
                    if last_login_days >= DAYS_THRESHOLD and key_last_used_days >= DAYS_THRESHOLD:
                        reasons.append(f"UI login last used {last_login_days} days ago.")
                        reasons.append(f"Access keys last used {key_last_used_days} days ago.")

                if reasons:
                    unused_users.append({
                        "UserName": user_name,
                        "UserId": user_arn,
                        "LastLogin": "Never" if last_login_days == -1 else f"{last_login_days} days ago",
                        "LastKeyUsage": "Never" if key_last_used_days == -1 else f"{key_last_used_days} days ago",
                        "AccountId": session.account_id,
                        "Reason": "\n".join(reasons),
                    })
                    logger.debug(f"Unused user identified: {user_name} - Reasons: {reasons}")

            logger.info(f"Found {len(unused_users)} unused IAM Users.")
            return unused_users

        except Exception as e:
            logger.error(f"Error during IAM user scan: {e}")
            return []

    @staticmethod
    def _get_latest_key_usage_days(iam_client, access_keys, current_time):
        """
        Retrieve the latest key usage days for a user based on access keys.

        :param iam_client: Boto3 IAM client.
        :param access_keys: List of access keys metadata for a user.
        :param current_time: Current UTC time for comparison.
        :return: Days since last access key usage or -1 if never used.
        """
        try:
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
