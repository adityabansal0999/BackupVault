
import os
from dotenv import load_dotenv

load_dotenv()


def _env_bool(name, default=False):
    """Read a boolean environment variable."""
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1", "true", "yes", "on"
    }


# ============================================================
# MYSQL CONFIGURATION
# ============================================================

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "backupvault_meta")

TARGET_DB_NAME = os.getenv(
    "TARGET_DB_NAME",
    "customer_db",
)


# ============================================================
# BACKUP CONFIGURATION
# ============================================================

BACKUP_DIR = os.getenv(
    "BACKUP_DIR",
    "./backups",
)

RETENTION_DAYS = int(
    os.getenv("RETENTION_DAYS", "90")
)


# ============================================================
# SCHEDULER CONFIGURATION
# ============================================================

CRON_EXPRESSION = os.getenv(
    "CRON_EXPRESSION",
    "0 2 * * *",
)

SCHEDULER_TIMEZONE = os.getenv(
    "SCHEDULER_TIMEZONE",
    "Asia/Kolkata",
)

CATCH_UP_HOURS = int(
    os.getenv("CATCH_UP_HOURS", "24")
)


# ============================================================
# ALERT RECIPIENT
# ============================================================

ALERT_EMAIL = os.getenv(
    "ALERT_EMAIL",
    "admin@company.com",
)


# ============================================================
# SMTP EMAIL CONFIGURATION
# ============================================================

SMTP_HOST = os.getenv(
    "SMTP_HOST",
    "",
).strip()

SMTP_PORT = int(
    os.getenv("SMTP_PORT", "587")
)

SMTP_USERNAME = os.getenv(
    "SMTP_USERNAME",
    "",
).strip()

SMTP_PASSWORD = os.getenv(
    "SMTP_PASSWORD",
    "",
)

SMTP_FROM_EMAIL = os.getenv(
    "SMTP_FROM_EMAIL",
    SMTP_USERNAME,
).strip()

SMTP_USE_TLS = _env_bool(
    "SMTP_USE_TLS",
    True,
)

SMTP_USE_SSL = _env_bool(
    "SMTP_USE_SSL",
    False,
)


# ============================================================
# AUTOMATED ALERT MONITORING
# ============================================================

NO_BACKUP_ALERT_HOURS = int(
    os.getenv("NO_BACKUP_ALERT_HOURS", "48")
)

STORAGE_ALERT_THRESHOLD_PERCENT = float(
    os.getenv("STORAGE_ALERT_THRESHOLD_PERCENT", "90")
)

STORAGE_ALERT_COOLDOWN_HOURS = int(
    os.getenv("STORAGE_ALERT_COOLDOWN_HOURS", "24")
)

ALERT_MONITOR_INTERVAL_MINUTES = int(
    os.getenv("ALERT_MONITOR_INTERVAL_MINUTES", "15")
)
