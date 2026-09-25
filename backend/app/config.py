# all settings come from the .env file, never hard-code passwords
import os
from dotenv import load_dotenv
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "backupvault_meta")  # metadata db
TARGET_DB_NAME = os.getenv("TARGET_DB_NAME", "customer_db")  # db that gets backed up
BACKUP_DIR = os.getenv("BACKUP_DIR", "./backups")
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "admin@company.com")

# schedule: "minute hour day month weekday". '0 2 * * *' = 02:00 every day, once daily
CRON_EXPRESSION = os.getenv("CRON_EXPRESSION", "0 2 * * *")
SCHEDULER_TIMEZONE = os.getenv("SCHEDULER_TIMEZONE", "Asia/Kolkata")
# if the app was off at backup time, run one backup on startup when the last good one is older than this
CATCH_UP_HOURS = int(os.getenv("CATCH_UP_HOURS", "24"))
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "90"))
